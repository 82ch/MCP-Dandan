/*
 * YARA Rules for Command Injection Detection
 * Extracted from command_injection_engine.py
 */

// ========== Critical Patterns ==========

rule Command_Chaining_Destructive
{
    meta:
        description = "Command chaining with destructive operation"
        category = "critical"
        severity = "high"
        reason = "Command chaining with destructive operation"
    strings:
        $chain1 = /;\s*(rm|del|format|mkfs)/ nocase
        $chain2 = /\|\s*(rm|del|format|mkfs)/ nocase
        $chain3 = /&&\s*(rm|del|format|mkfs)/ nocase
    condition:
        any of them
}

rule Command_Substitution_Destructive
{
    meta:
        description = "Command substitution with destructive operation"
        category = "critical"
        severity = "high"
        reason = "Command substitution with destructive operation"
    strings:
        $sub1 = /\$\(.*rm.*\)/ nocase
        $sub2 = /`.*rm.*`/ nocase
    condition:
        any of them
}

rule Dynamic_Code_Execution
{
    meta:
        description = "Dynamic code evaluation and execution"
        category = "critical"
        severity = "high"
    strings:
        $eval = /eval\s*\(/ nocase
        $exec = /exec\s*\(/ nocase
        $system = /system\s*\(/ nocase
        $popen = /popen\s*\(/ nocase
        $subprocess = /subprocess\.(call|run|Popen)/ nocase
        $os_system = "os.system" nocase
        $shell = "shell=True" nocase
    condition:
        any of them
}

rule Privilege_Escalation
{
    meta:
        description = "Privilege escalation attempt"
        category = "critical"
        severity = "high"
        reason = "Privilege escalation attempt"
    strings:
        $sudo = /sudo\s+/ nocase
        $su = /su\s+-/ nocase
        $runas = /runas\s+/ nocase
    condition:
        any of them
}

rule Data_Exfiltration
{
    meta:
        description = "Data exfiltration via network tools"
        category = "critical"
        severity = "high"
        reason = "Data exfiltration attempt"
    strings:
        $nc1 = /\|\s*nc\s+/ nocase
        $nc2 = /\|\s*netcat\s+/ nocase
        $tcp = />\s*\/dev\/tcp\// nocase
        $curl = /curl.*-d\s*@/ nocase
        $wget = /wget.*-O.*-/ nocase
    condition:
        any of them
}

// ========== High-Risk Patterns ==========

rule Shell_Metachar_Dangerous_Commands
{
    meta:
        description = "Shell metacharacter with dangerous commands"
        category = "high"
        severity = "high"
        reason = "Command chaining with dangerous command"
    strings:
        $chain1 = /;\s*(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)/ nocase
        $chain2 = /&&\s*(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)/ nocase
        $chain3 = /\|\s*(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)/ nocase
        $chain4 = /`[^`]*\b(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)\b[^`]*`/ nocase
    condition:
        any of them
}

rule Command_Substitution_Dangerous
{
    meta:
        description = "Command substitution with dangerous commands"
        category = "high"
        severity = "high"
        reason = "Command substitution with dangerous command"
    strings:
        $sub1 = /\$\{[^}]*(rm|del|wget|curl|bash|sh|cmd)[^}]*\}/ nocase
        $sub2 = /\$\([^)]*(rm|del|wget|curl|bash|sh|cmd)[^)]*\)/ nocase
    condition:
        any of them
}

rule Environment_Variable_Abuse
{
    meta:
        description = "Environment variable manipulation"
        category = "high"
        severity = "high"
    strings:
        $comspec = "%COMSPEC%" nocase
        $sysroot = "%SYSTEMROOT%" nocase
        $path = /\$PATH\s*=/ nocase
        $preload = "$LD_PRELOAD" nocase
    condition:
        any of them
}

rule Script_Injection
{
    meta:
        description = "Script injection attempt"
        category = "high"
        severity = "high"
        reason = "Script injection attempt"
    strings:
        $script = "<script" nocase
        $javascript = "javascript:" nocase
        $onerror = /onerror\s*=/ nocase
        $onload = /onload\s*=/ nocase
    condition:
        any of them
}

// ========== Medium-Risk Patterns ==========

rule Common_Shell_Commands
{
    meta:
        description = "Common shell command interpreters"
        category = "medium"
        severity = "medium"
    strings:
        $cmd = /\bcmd\b/ nocase
        $sh = /\bsh\b/ nocase
        $bash = /\bbash\b/ nocase
        $powershell = /\bpowershell\b/ nocase
        $wmic = /\bwmic\b/ nocase
    condition:
        any of them
}

rule File_Operations
{
    meta:
        description = "File operation commands"
        category = "medium"
        severity = "medium"
        reason = "File operation command"
    strings:
        $move = /\bmove\b/ nocase
        $copy = /\bcopy\b/ nocase
        $cp = /\bcp\b/ nocase
        $mv = /\bmv\b/ nocase
    condition:
        any of them
}

rule Network_Commands
{
    meta:
        description = "Network-related commands"
        category = "medium"
        severity = "medium"
        reason = "Network command"
    strings:
        $ping = /\bping\b.*-[tn]\s+\d+/ nocase
        $telnet = /\btelnet\b/ nocase
        $ftp = /\bftp\b/ nocase
    condition:
        any of them
}

// ========== Dangerous Commands ==========

rule Dangerous_System_Commands
{
    meta:
        description = "Potentially dangerous system commands"
        category = "high"
        severity = "high"
        reason = "Potentially dangerous command"
    strings:
        $rm = /\brm\b/ nocase
        $del = /\bdel\b/ nocase
        $format = /\bformat\b/ nocase
        $mkfs = /\bmkfs\b/ nocase
        $dd = /\bdd\b/ nocase
        $fdisk = /\bfdisk\b/ nocase
        $kill = /\bkill\b/ nocase
        $killall = /\bkillall\b/ nocase
        $taskkill = /\btaskkill\b/ nocase
    condition:
        any of them
}

rule Dangerous_Network_Commands
{
    meta:
        description = "Dangerous network/download commands"
        category = "high"
        severity = "high"
        reason = "Potentially dangerous network command"
    strings:
        $wget = /\bwget\b/ nocase
        $curl = /\bcurl\b/ nocase
        $nc = /\bnc\b/ nocase
        $netcat = /\bnetcat\b/ nocase
    condition:
        any of them
}

rule Dangerous_Permission_Commands
{
    meta:
        description = "Permission/ownership modification commands"
        category = "high"
        severity = "high"
        reason = "Permission modification command"
    strings:
        $chmod = /\bchmod\b/ nocase
        $chown = /\bchown\b/ nocase
        $icacls = /\bicacls\b/ nocase
    condition:
        any of them
}

rule Dangerous_Registry_Commands
{
    meta:
        description = "Windows registry manipulation"
        category = "high"
        severity = "high"
        reason = "Registry manipulation command"
    strings:
        $reg = /\breg\b/ nocase
        $regedit = /\bregedit\b/ nocase
    condition:
        any of them
}

rule Dangerous_Network_Config
{
    meta:
        description = "Network configuration commands"
        category = "high"
        severity = "high"
        reason = "Network configuration command"
    strings:
        $net = /\bnet\b/ nocase
        $netsh = /\bnetsh\b/ nocase
    condition:
        any of them
}
