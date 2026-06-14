param(
    [Parameter(Mandatory = $true)]
    [int]$TaskCount,
    [int]$SamplesPerTask = 25,
    [string]$SourcePath = "RQ2\data\mbpp_rq2_transformed.jsonl",
    [string]$SampleCodeFile = "RQ2\data\mbpp_rq2_sample_25.jsonl",
    [string]$OutputDir = "RQ2\data",
    [string]$Prefix = ""
)

if (-not $Prefix) {
    $Prefix = "mbpp_rq2_first_$TaskCount"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$sourceRows = @(Get-Content $SourcePath | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
$sampleRows = @(Get-Content $SampleCodeFile | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
$samplesByTask = @{}

foreach ($row in $sampleRows) {
    $key = [string]$row.task_id
    if (-not $samplesByTask.ContainsKey($key)) {
        $samplesByTask[$key] = New-Object System.Collections.Generic.List[object]
    }
    $samplesByTask[$key].Add($row)
}

$selectedSource = New-Object System.Collections.Generic.List[object]
$greedyRows = New-Object System.Collections.Generic.List[object]

foreach ($source in $sourceRows) {
    $key = [string]$source.task_id
    if (-not $samplesByTask.ContainsKey($key)) {
        continue
    }
    $taskSamples = $samplesByTask[$key]
    if ($taskSamples.Count -lt $SamplesPerTask) {
        continue
    }

    $selectedSource.Add($source)
    $firstSample = $taskSamples[0].raw_code_completion
    $greedyRows.Add([pscustomobject]@{
        task_id = $source.task_id
        prompt = $source.prompt
        raw_code_completion = $firstSample
        samples = @($firstSample)
    })

    if ($selectedSource.Count -eq $TaskCount) {
        break
    }
}

if ($selectedSource.Count -lt $TaskCount) {
    throw "Only found $($selectedSource.Count) tasks with at least $SamplesPerTask samples. Requested $TaskCount."
}

$sourceOut = Join-Path $OutputDir "$Prefix`_source.jsonl"
$greedyOut = Join-Path $OutputDir "$Prefix`_greedy.jsonl"

$selectedSource | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 20 } | Set-Content -Encoding utf8 $sourceOut
$greedyRows | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 20 } | Set-Content -Encoding utf8 $greedyOut

Write-Host "[RQ2] Wrote source subset: $sourceOut"
Write-Host "[RQ2] Wrote greedy baseline: $greedyOut"
