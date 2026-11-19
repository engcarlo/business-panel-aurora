# Abre a planilha no Excel (oculto), recalcula, mostra os KPIs, confere se os
# gráficos têm pontos e exporta a aba Dashboard em PDF. Não salva a planilha.
param([Parameter(Mandatory)][string]$Planilha, [Parameter(Mandatory)][string]$Pdf)
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
    $wb = $xl.Workbooks.Open((Resolve-Path $Planilha).Path, 0, $true)
    $xl.CalculateFull()
    $ws = $wb.Worksheets.Item("Dashboard")
    foreach ($c in @("B4","B5","G4","G5","L4","L5","Q4","Q5","Q6","V4","V5","V6")) {
        "{0,-4} {1}" -f $c, $ws.Range($c).Text
    }
    foreach ($co in $ws.ChartObjects()) {
        $s = $co.Chart.SeriesCollection(1)
        $vals = @($s.Values) | Where-Object { $_ -ne $null -and $_ -ne 0 }
        "Grafico '{0}': {1} barras com valor" -f $co.Chart.ChartTitle.Text, $vals.Count
    }
    $pp = $ws.PageSetup
    "Paginas p/ impressao: {0}  (orientacao {1})" -f $ws.HPageBreaks.Count, $pp.Orientation
    $ws.ExportAsFixedFormat(0, $Pdf)
    "PDF: $Pdf"
    $wb.Close($false)
} finally { $xl.Quit(); [System.Runtime.Interopservices.Marshal]::ReleaseComObject($xl) | Out-Null }
