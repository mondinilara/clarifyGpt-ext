param(
    [string]$InputPath = "src\data\mbpp_sanitized_microsoft.jsonl",
    [string]$OutputDir = "RQ2\data",
    [int]$Limit = 0
)

function Split-TopLevel([string]$Text) {
    $parts = New-Object System.Collections.Generic.List[string]
    $current = ""
    $depth = 0
    $quote = $null
    $escape = $false
    foreach ($ch in $Text.ToCharArray()) {
        if ($quote) {
            $current += $ch
            if ($escape) { $escape = $false }
            elseif ($ch -eq "\") { $escape = $true }
            elseif ($ch -eq $quote) { $quote = $null }
            continue
        }
        if ($ch -eq "'" -or $ch -eq '"') { $quote = $ch; $current += $ch; continue }
        if ("([{".Contains($ch)) { $depth += 1; $current += $ch; continue }
        if (")]}".Contains($ch)) { $depth -= 1; $current += $ch; continue }
        if ($ch -eq "," -and $depth -eq 0) {
            $parts.Add($current)
            $current = ""
            continue
        }
        $current += $ch
    }
    $parts.Add($current)
    return $parts
}

function Replace-Identifier([string]$Text, [string]$Old, [string]$New) {
    return [regex]::Replace($Text, "\b$([regex]::Escape($Old))\b", $New)
}

function Rewrite-Docstring([string]$Text) {
    $rewritten = $Text
    $pairs = @(
        @("Write a python function to ", "Implement a Python routine that "),
        @("Write a function to ", "Implement a function that "),
        @("Write a python function which ", "Implement a Python routine that "),
        @("Write a function which ", "Implement a function that "),
        @("Write a program to ", "Create code that "),
        @("given ", "provided "),
        @("the given ", "the supplied "),
        @("find ", "compute "),
        @("check whether ", "determine whether "),
        @("check if ", "determine if "),
        @("returns ", "produces "),
        @("return ", "produce ")
    )
    foreach ($pair in $pairs) {
        $rewritten = $rewritten.Replace($pair[0], $pair[1])
    }
    if ($rewritten -eq $Text) {
        $rewritten = "Solve the task described here: $rewritten"
    }
    return $rewritten.Trim()
}

function Transform-Calls([string]$Text, [string]$OldName, [string]$NewName, [bool]$ReverseArgs) {
    $result = ""
    $i = 0
    $needle = "$OldName("
    while ($i -lt $Text.Length) {
        $idx = $Text.IndexOf($needle, $i)
        if ($idx -lt 0) {
            $result += $Text.Substring($i)
            break
        }
        if ($idx -gt 0 -and $Text[$idx - 1] -match "\w") {
            $result += $Text.Substring($i, $idx + $OldName.Length - $i)
            $i = $idx + $OldName.Length
            continue
        }
        $result += $Text.Substring($i, $idx - $i) + "$NewName("
        $start = $idx + $OldName.Length + 1
        $depth = 1
        $quote = $null
        $escape = $false
        $j = $start
        while ($j -lt $Text.Length) {
            $ch = $Text[$j]
            if ($quote) {
                if ($escape) { $escape = $false }
                elseif ($ch -eq "\") { $escape = $true }
                elseif ($ch -eq $quote) { $quote = $null }
                $j += 1
                continue
            }
            if ($ch -eq "'" -or $ch -eq '"') { $quote = $ch; $j += 1; continue }
            if ($ch -eq "(") { $depth += 1 }
            elseif ($ch -eq ")") {
                $depth -= 1
                if ($depth -eq 0) { break }
            }
            $j += 1
        }
        $inside = $Text.Substring($start, $j - $start)
        $args = @(Split-TopLevel $inside | ForEach-Object { $_.Trim() } | Where-Object { $_.Length -gt 0 })
        if ($ReverseArgs -and $args.Count -ge 2) {
            [array]::Reverse($args)
        }
        $result += ($args -join ", ") + ")"
        $i = $j + 1
    }
    return $result
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$rows = Get-Content $InputPath | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json }
if ($Limit -gt 0) {
    $rows = @($rows | Select-Object -First $Limit)
}

$transformedRows = New-Object System.Collections.Generic.List[object]
$reportRows = New-Object System.Collections.Generic.List[object]

foreach ($row in $rows) {
    $firstLine = ($row.prompt.Trim() -split "`n")[0].Trim()
    $match = [regex]::Match($firstLine, "^def\s+([A-Za-z_]\w*)\s*\((.*)\)\s*:")
    if (-not $match.Success) {
        throw "Could not parse signature: $firstLine"
    }

    $oldName = $match.Groups[1].Value
    $oldArgsRaw = $match.Groups[2].Value.Trim()
    $oldArgs = @()
    if ($oldArgsRaw.Length -gt 0) {
        $oldArgs = @(Split-TopLevel $oldArgsRaw | ForEach-Object { ($_.Trim() -split "=")[0].Trim() } | Where-Object { $_ })
    }

    $newName = "rq2_task_$($row.task_id)"
    $renamedArgs = @(for ($idx = 0; $idx -lt $oldArgs.Count; $idx++) { "rq2_arg_$($idx + 1)" })
    $reverseArgs = $renamedArgs.Count -ge 2
    $promptArgs = @($renamedArgs)
    if ($reverseArgs) { [array]::Reverse($promptArgs) }

    $docMatch = [regex]::Match($row.prompt, "'''([\s\S]*?)'''")
    $doc = if ($docMatch.Success) { $docMatch.Groups[1].Value } else { " Implement the requested behavior. " }
    $newDoc = Rewrite-Docstring $doc

    $newRow = [ordered]@{}
    foreach ($prop in $row.PSObject.Properties) {
        $newRow[$prop.Name] = $prop.Value
    }
    $newRow["prompt"] = "def $newName($($promptArgs -join ', ')):`n    '''`n$newDoc`n    '''"
    $newRow["entry_point"] = $newName

    $newTests = @()
    foreach ($test in $row.tests) {
        $text = Transform-Calls $test $oldName $newName $reverseArgs
        for ($idx = 0; $idx -lt $oldArgs.Count; $idx++) {
            $text = Replace-Identifier $text $oldArgs[$idx] $renamedArgs[$idx]
        }
        $newTests += $text
    }
    $newTestList = @()
    foreach ($test in $row.test_list) {
        $text = Transform-Calls $test $oldName $newName $reverseArgs
        for ($idx = 0; $idx -lt $oldArgs.Count; $idx++) {
            $text = Replace-Identifier $text $oldArgs[$idx] $renamedArgs[$idx]
        }
        $newTestList += $text
    }
    $newRow["tests"] = $newTests
    $newRow["test_list"] = $newTestList
    $newRow["test"] = $newTestList -join "`n"

    $solution = [string]$row.solution
    $solution = Replace-Identifier $solution $oldName $newName
    for ($idx = 0; $idx -lt $oldArgs.Count; $idx++) {
        $solution = Replace-Identifier $solution $oldArgs[$idx] $renamedArgs[$idx]
    }
    $solution = [regex]::Replace(
        $solution,
        "def\s+$([regex]::Escape($newName))\s*\([^)]*\)\s*:",
        "def $newName($($promptArgs -join ', ')):",
        1
    )
    $newRow["solution"] = $solution

    $transformedRows.Add([pscustomobject]$newRow)
    $reportRows.Add([pscustomobject]@{
        task_id = $row.task_id
        old_entry_point = $oldName
        new_entry_point = $newName
        old_args = $oldArgs
        renamed_args = $renamedArgs
        prompt_arg_order = $promptArgs
        function_renamed = $oldName -ne $newName
        arguments_renamed = ($oldArgs -join "|") -ne ($renamedArgs -join "|")
        arguments_reordered_in_prompt = $reverseArgs
        docstring_paraphrased = $true
    })
}

$transformedPath = Join-Path $OutputDir "mbpp_rq2_transformed.jsonl"
$testsPath = Join-Path $OutputDir "mbpp_rq2_tests_final.jsonl"
$reportPath = Join-Path $OutputDir "mbpp_rq2_transform_report.jsonl"
$summaryPath = Join-Path $OutputDir "mbpp_rq2_summary.json"

$transformedRows | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 20 } | Set-Content -Encoding utf8 $transformedPath
$transformedRows | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 20 } | Set-Content -Encoding utf8 $testsPath
$reportRows | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 20 } | Set-Content -Encoding utf8 $reportPath

[pscustomobject]@{
    source = $InputPath
    task_count = $transformedRows.Count
    outputs = [pscustomobject]@{
        source = $transformedPath
        tests = $testsPath
        report = $reportPath
    }
    transformations = @(
        "function entry_point renamed to rq2_task_<task_id>",
        "all formal parameters renamed to rq2_arg_<position>",
        "formal parameter order reversed in the prompt when the function has at least two parameters",
        "test calls updated to use the renamed function and reversed positional arguments",
        "docstring paraphrased with deterministic lexical rewrites"
    )
} | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $summaryPath

Write-Host "[RQ2] Wrote $($transformedRows.Count) transformed tasks to $OutputDir"
