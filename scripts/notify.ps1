# Windows toast for tier-harness. Usage: powershell -File notify.ps1 -Title "<title>" -Body "<body>"
# No modules needed. Falls back silently if the WinRT toast API is unavailable.
param(
  [string]$Title = "tier-harness",
  [string]$Body = ""
)
try {
  [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
  [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
  $esc = [System.Security.SecurityElement]::Escape
  $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
  $xml.LoadXml("<toast><visual><binding template=""ToastGeneric""><text>$($esc.Invoke($Title))</text><text>$($esc.Invoke($Body))</text></binding></visual></toast>")
  $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
  $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
  Write-Output "notified"
} catch {
  Write-Output "notify skipped: $($_.Exception.Message)"
}
