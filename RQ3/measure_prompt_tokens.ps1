param(
    [string]$OriginalPath = "src\prompt\prompt_mbpp.py",
    [string]$OptimizedPath = "RQ3\prompt_mbpp_optimized.py",
    [string]$OutputPath = "RQ3\token_reduction_report.json"
)

function Get-Block([string]$Text, [string]$VariableName, [bool]$AssignmentStyle = $false) {
    $varIndex = $Text.IndexOf("$VariableName =")
    if ($varIndex -lt 0) {
        throw "Variable not found: $VariableName"
    }

    if ($AssignmentStyle) {
        $stageIndex = $Text.IndexOf("$VariableName[`"three_shot`"]", $varIndex)
        if ($stageIndex -lt 0) {
            $stageIndex = $Text.IndexOf("$VariableName['three_shot']", $varIndex)
        }
    } else {
        $stageIndex = $Text.IndexOf('"three_shot"', $varIndex)
        if ($stageIndex -lt 0) {
            $stageIndex = $Text.IndexOf("'three_shot'", $varIndex)
        }
    }
    if ($stageIndex -lt 0) {
        throw "three_shot not found for $VariableName"
    }

    if ($AssignmentStyle) {
        $equalsIndex = $Text.IndexOf("=", $stageIndex)
        if ($equalsIndex -lt 0) {
            throw "Assignment not found for $VariableName"
        }
        $openIndex = $Text.IndexOf("[", $equalsIndex)
    } else {
        $openIndex = $Text.IndexOf("[", $stageIndex)
    }
    if ($openIndex -lt 0) {
        throw "Opening list not found for $VariableName"
    }

    $depth = 0
    $quote = $null
    $escape = $false
    for ($i = $openIndex; $i -lt $Text.Length; $i++) {
        $ch = $Text[$i]
        if ($quote) {
            if ($escape) { $escape = $false }
            elseif ($ch -eq "\") { $escape = $true }
            elseif ($ch -eq $quote) { $quote = $null }
            continue
        }
        if ($ch -eq "'" -or $ch -eq '"') {
            $quote = $ch
            continue
        }
        if ($ch -eq "[") { $depth += 1 }
        elseif ($ch -eq "]") {
            $depth -= 1
            if ($depth -eq 0) {
                return $Text.Substring($openIndex, $i - $openIndex + 1)
            }
        }
    }
    throw "Could not close block for $VariableName"
}

function Count-TokenEstimate([string]$Text) {
    return ([regex]::Matches($Text, "\w+|[^\w\s]")).Count
}

$originalText = Get-Content $OriginalPath -Raw
$optimizedText = Get-Content $OptimizedPath -Raw

$items = @(
    @{ stage = "askcq"; variable = "askcq_prompt" },
    @{ stage = "answercq"; variable = "answercq_prompt" },
    @{ stage = "synthesize"; variable = "synthesize_prompt" }
)

$rows = @()
$totalOriginal = 0
$totalOptimized = 0

foreach ($item in $items) {
    $originalBlock = Get-Block $originalText $item.variable $false
    $optimizedBlock = Get-Block $optimizedText $item.variable $true
    $originalTokens = Count-TokenEstimate $originalBlock
    $optimizedTokens = Count-TokenEstimate $optimizedBlock
    $totalOriginal += $originalTokens
    $totalOptimized += $optimizedTokens
    $rows += [pscustomobject]@{
        stage = $item.stage
        original_tokens = $originalTokens
        optimized_tokens = $optimizedTokens
        reduced_tokens = $originalTokens - $optimizedTokens
        reduction_percent = [math]::Round((1 - ($optimizedTokens / $originalTokens)) * 100, 2)
    }
}

$summary = [pscustomobject]@{
    tokenizer = "regex_estimate"
    inference_type = "three_shot"
    stages = $rows
    total_original_tokens = $totalOriginal
    total_optimized_tokens = $totalOptimized
    total_reduced_tokens = $totalOriginal - $totalOptimized
    total_reduction_percent = [math]::Round((1 - ($totalOptimized / $totalOriginal)) * 100, 2)
    note = "Fallback estimate over static three_shot prompt definitions. Run measure_prompt_tokens.py with tiktoken installed for OpenAI tokenizer counts."
}

$summary | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $OutputPath
$summary | ConvertTo-Json -Depth 10
