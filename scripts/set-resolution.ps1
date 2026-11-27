# iPad Monitor - forzar resolucion de un monitor virtual a 1024x768
# Uso: .\scripts\set-resolution.ps1 [-Monitor 3] [-Name "Virtual Display Driver"]

param(
    [int]$Monitor = 0,
    [string]$Name = "Virtual"
)

$targetW = 1024
$targetH = 768

Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class DisplaySettings {
    [DllImport("user32.dll", CharSet = CharSet.Ansi)]
    public static extern int EnumDisplaySettings(string deviceName, int modeNum, ref DEVMODE devMode);

    [DllImport("user32.dll", CharSet = CharSet.Ansi)]
    public static extern int ChangeDisplaySettingsEx(string deviceName, ref DEVMODE devMode, IntPtr hwnd, int flags, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Ansi)]
    public static extern bool EnumDisplayDevices(string lpDevice, uint iDevNum, ref DISPLAY_DEVICE lpDisplayDevice, uint dwFlags);

    public const int CDS_UPDATEREGISTRY = 0x01;
    public const int CDS_TEST = 0x02;
    public const int DISP_CHANGE_SUCCESSFUL = 0;
    public const int DISP_CHANGE_BADMODE = -2;
    public const int ENUM_CURRENT_SETTINGS = -1;
    public const int ENUM_REGISTRY_SETTINGS = -2;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    public struct DEVMODE {
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string dmDeviceName;
        public short dmSpecVersion;
        public short dmDriverVersion;
        public short dmSize;
        public short dmDriverExtra;
        public int dmFields;
        public int dmPositionX;
        public int dmPositionY;
        public int dmDisplayOrientation;
        public int dmDisplayFixedOutput;
        public short dmColor;
        public short dmDuplex;
        public short dmYResolution;
        public short dmTTOption;
        public short dmCollate;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string dmFormName;
        public short dmLogPixels;
        public int dmBitsPerPel;
        public int dmPelsWidth;
        public int dmPelsHeight;
        public int dmDisplayFlags;
        public int dmDisplayFrequency;
        public int dmICMMethod;
        public int dmICMIntent;
        public int dmMediaType;
        public int dmDitherType;
        public int dmReserved1;
        public int dmReserved2;
        public int dmPanningWidth;
        public int dmPanningHeight;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    public struct DISPLAY_DEVICE {
        public int cb;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string DeviceName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
        public string DeviceString;
        public int StateFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
        public string DeviceID;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
        public string DeviceKey;
    }
}
"@

function Get-VideoControllers() {
    try {
        return @(Get-CimInstance Win32_VideoController -ErrorAction Stop | ForEach-Object {
            New-Object PSObject -Property @{
                Name = $_.Name
                CurrentWidth = $_.CurrentHorizontalResolution
                CurrentHeight = $_.CurrentVerticalResolution
                DeviceName = $null
            }
        })
    } catch {
        return @()
    }
}

function Get-DisplayDeviceName($index) {
    $device = New-Object DisplaySettings+DISPLAY_DEVICE
    $device.cb = [System.Runtime.InteropServices.Marshal]::SizeOf($device)
    if ([DisplaySettings]::EnumDisplayDevices($null, [uint32]($index - 1), [ref]$device, 0)) {
        return $device.DeviceName
    }
    return $null
}

try {
    $controllers = Get-VideoControllers
    if ($controllers.Count -eq 0) {
        Write-Host "No se pudieron detectar controladores de video." -ForegroundColor Red
        exit 1
    }

    $selectedIndex = 0
    $selectedDeviceName = $null

    if ($Monitor -gt 0 -and $Monitor -le $controllers.Count) {
        $selectedIndex = $Monitor
        $selectedDeviceName = Get-DisplayDeviceName($Monitor)
        if (-not $selectedDeviceName) {
            # fallback: asumir \\.\DISPLAY{index}
            $selectedDeviceName = "\\.\DISPLAY" + $Monitor
        }
    } else {
        # Buscar por nombre
        for ($i = 0; $i -lt $controllers.Count; $i++) {
            if ($controllers[$i].Name -like "*$Name*") {
                $selectedIndex = $i + 1
                $selectedDeviceName = Get-DisplayDeviceName($selectedIndex)
                if (-not $selectedDeviceName) {
                    $selectedDeviceName = "\\.\DISPLAY" + $selectedIndex
                }
                break
            }
        }
    }

    if ($selectedIndex -eq 0) {
        Write-Host "No se encontro un monitor virtual con el nombre '*$Name*'." -ForegroundColor Red
        Write-Host "Controladores detectados:"
        for ($i = 0; $i -lt $controllers.Count; $i++) {
            Write-Host "  $($i + 1). $($controllers[$i].Name) - $($controllers[$i].CurrentWidth)x$($controllers[$i].CurrentHeight)"
        }
        Write-Host ""
        Write-Host "Proba ejecutar con: .\set-resolution.ps1 -Monitor 3"
        exit 1
    }

    Write-Host "Monitor seleccionado: #$selectedIndex - $($controllers[$selectedIndex - 1].Name)"
    Write-Host "Dispositivo: $selectedDeviceName"

    $mode = New-Object DisplaySettings+DEVMODE
    $mode.dmSize = [System.Runtime.InteropServices.Marshal]::SizeOf($mode)

    $bestMode = $null
    $modeIndex = 0
    while ([DisplaySettings]::EnumDisplaySettings($selectedDeviceName, $modeIndex, [ref]$mode) -ne 0) {
        if ($mode.dmPelsWidth -eq $targetW -and $mode.dmPelsHeight -eq $targetH) {
            $bestMode = $mode
            break
        }
        $modeIndex++
        $mode = New-Object DisplaySettings+DEVMODE
        $mode.dmSize = [System.Runtime.InteropServices.Marshal]::SizeOf($mode)
    }

    if ($null -eq $bestMode) {
        Write-Host "El monitor #$selectedIndex no expone la resolucion ${targetW}x${targetH} en su lista." -ForegroundColor Yellow
        Write-Host "Intentando aplicar un modo manual..." -ForegroundColor Yellow
        $mode = New-Object DisplaySettings+DEVMODE
        $mode.dmSize = [System.Runtime.InteropServices.Marshal]::SizeOf($mode)
        $mode.dmFields = 0x00000004 -bor 0x00000008 -bor 0x00000040 -bor 0x00100000  # DM_PELSWIDTH | DM_PELSHEIGHT | DM_BITSPERPEL | DM_DISPLAYFREQUENCY
        $mode.dmPelsWidth = $targetW
        $mode.dmPelsHeight = $targetH
        $mode.dmBitsPerPel = 32
        $mode.dmDisplayFrequency = 60
        $bestMode = $mode
    }

    Write-Host "Aplicando ${targetW}x${targetH}..."
    $result = [DisplaySettings]::ChangeDisplaySettingsEx($selectedDeviceName, [ref]$bestMode, [IntPtr]::Zero, [DisplaySettings]::CDS_UPDATEREGISTRY, [IntPtr]::Zero)
    if ($result -eq [DisplaySettings]::DISP_CHANGE_SUCCESSFUL) {
        Write-Host "Resolucion aplicada con exito." -ForegroundColor Green
        exit 0
    } else {
        Write-Host "No se pudo aplicar (codigo $result)." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}
