# iPad Monitor — listar monitores detectados por Windows
# Uso: .\scripts\list-monitors.ps1

param(
    [switch]$Silent
)

function Write-Info($msg, $color = "White") {
    if (-not $Silent) {
        Write-Host $msg -ForegroundColor $color
    }
}

# Metodo 1: P/Invoke EnumDisplayDevices
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class DisplayDevices {
    [DllImport("user32.dll", CharSet = CharSet.Ansi)]
    public static extern bool EnumDisplayDevices(string lpDevice, uint iDevNum, ref DISPLAY_DEVICE lpDisplayDevice, uint dwFlags);

    [DllImport("user32.dll", CharSet = CharSet.Ansi)]
    public static extern int EnumDisplaySettings(string deviceName, int modeNum, ref DEVMODE devMode);

    public const int ENUM_CURRENT_SETTINGS = -1;

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
    }
}
"@

$foundAny = $false

Write-Info "Metodo 1: EnumDisplayDevices (P/Invoke)" "Cyan"

try {
    $device = New-Object DisplayDevices+DISPLAY_DEVICE
    $device.cb = [System.Runtime.InteropServices.Marshal]::SizeOf($device)

    $index = 0
    while ([DisplayDevices]::EnumDisplayDevices($null, [uint32]$index, [ref]$device, 0)) {
        $mode = New-Object DisplayDevices+DEVMODE
        $mode.dmSize = [System.Runtime.InteropServices.Marshal]::SizeOf($mode)
        [DisplayDevices]::EnumDisplaySettings($device.DeviceName, [DisplayDevices]::ENUM_CURRENT_SETTINGS, [ref]$mode) | Out-Null

        $flags = @()
        if ($device.StateFlags -band 0x00000001) { $flags += "Principal" }
        if ($device.StateFlags -band 0x00000004) { $flags += "Externo" }
        if ($device.StateFlags -band 0x00000008) { $flags += "ModoSeguro" }
        if ($flags.Count -eq 0) { $flags = @("-") }

        Write-Info "  Monitor $($index + 1):" "Yellow"
        Write-Info "    Nombre:  $($device.DeviceName)"
        Write-Info "    Driver:  $($device.DeviceString)"
        Write-Info "    Estado:  $($flags -join ', ')"
        Write-Info "    Actual:  $($mode.dmPelsWidth)x$($mode.dmPelsHeight) @ $($mode.dmDisplayFrequency)Hz"
        $foundAny = $true

        $index++
        $device = New-Object DisplayDevices+DISPLAY_DEVICE
        $device.cb = [System.Runtime.InteropServices.Marshal]::SizeOf($device)
    }

    if ($index -eq 0) {
        Write-Info "  No se detectaron monitores con este metodo." "Yellow"
    }
} catch {
    Write-Info "  Error: $_" "Red"
}

Write-Info ""
Write-Info "Metodo 2: Win32_DesktopMonitor (WMI)" "Cyan"

try {
    $monitors = Get-CimInstance Win32_DesktopMonitor -ErrorAction Stop
    if ($monitors) {
        $i = 1
        foreach ($mon in $monitors) {
            Write-Info "  Monitor $($i):" "Yellow"
            Write-Info "    Nombre:  $($mon.Name)"
            Write-Info "    Estado:  $($mon.Status)"
            Write-Info "    Resolucion:  $($mon.ScreenWidth)x$($mon.ScreenHeight)"
            $foundAny = $true
            $i++
        }
    } else {
        Write-Info "  No se detectaron monitores con este metodo." "Yellow"
    }
} catch {
    Write-Info "  Error: $_" "Red"
}

Write-Info ""
Write-Info "Metodo 3: Win32_VideoController (WMI)" "Cyan"

try {
    $controllers = Get-CimInstance Win32_VideoController -ErrorAction Stop
    if ($controllers) {
        $i = 1
        foreach ($c in $controllers) {
            Write-Info "  Controlador $($i):" "Yellow"
            Write-Info "    Nombre:  $($c.Name)"
            Write-Info "    Resolucion actual:  $($c.CurrentHorizontalResolution)x$($c.CurrentVerticalResolution)"
            Write-Info "    Resoluciones soportadas:  $($c.VideoModeDescription)"
            $foundAny = $true
            $i++
        }
    } else {
        Write-Info "  No se detectaron controladores con este metodo." "Yellow"
    }
} catch {
    Write-Info "  Error: $_" "Red"
}

Write-Info ""
if ($foundAny) {
    Write-Info "Si ves un monitor virtual, anota su numero y usalo en set-resolution.bat" "Green"
} else {
    Write-Info "No se detecto ningun monitor con ningun metodo." "Red"
    Write-Info "Verifica que el driver virtual este instalado y que Windows lo vea en Configuracion de pantalla." "Yellow"
}

if ($foundAny) { exit 0 } else { exit 1 }
