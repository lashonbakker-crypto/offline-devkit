# Run from the repository root with PowerShell 7 (pwsh), not Windows PowerShell 5.1.
param(
    [ValidateSet('valid', 'invalid', 'producer-failure')]
    [string] $Mode = 'valid',
    [string] $Python = 'python'
)

$ErrorActionPreference = 'Stop'
# Expected native failures are inspected below instead of becoming terminating errors.
$PSNativeCommandUseErrorActionPreference = $false
$previousOutputEncoding = $OutputEncoding
$previousConsoleOutputEncoding = [Console]::OutputEncoding
$previousConsoleInputEncoding = [Console]::InputEncoding
$devkitUtf8 = [System.Text.UTF8Encoding]::new($false)
$producerArguments = @()
if ($Mode -eq 'invalid') { $producerArguments = @('--invalid') }
if ($Mode -eq 'producer-failure') { $producerArguments = @('--fail') }
$script:devkitProducerExit = $null
$devkitPipelineExit = 1

try {
    $OutputEncoding = $devkitUtf8
    [Console]::OutputEncoding = $devkitUtf8
    [Console]::InputEncoding = $devkitUtf8
    & {
        & $Python examples/produce_jsonl.py @producerArguments
        $script:devkitProducerExit = $LASTEXITCODE
    } | & $Python -m offline_devkit jsonl --json
    $devkitValidatorExit = $LASTEXITCODE
    if ($null -eq $script:devkitProducerExit) { throw 'Producer did not finish' }
    [Console]::Error.WriteLine("producer_exit=$script:devkitProducerExit validator_exit=$devkitValidatorExit")
    if ($script:devkitProducerExit -ne 0) {
        $devkitPipelineExit = $script:devkitProducerExit
    } else {
        $devkitPipelineExit = $devkitValidatorExit
    }
} finally {
    $OutputEncoding = $previousOutputEncoding
    [Console]::OutputEncoding = $previousConsoleOutputEncoding
    [Console]::InputEncoding = $previousConsoleInputEncoding
}
exit $devkitPipelineExit
