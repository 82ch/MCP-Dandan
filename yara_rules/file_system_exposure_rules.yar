/*
 * YARA Rules for File System Exposure Detection
 * Extracted from file_system_exposure_engine.py
 */

// ========== Critical System Paths ==========

rule Critical_Windows_System_Path
{
    meta:
        description = "Windows system path access"
        category = "critical"
        score = 50
        severity = "windows"
    strings:
        $path1 = "C:\\Windows\\System32" nocase
        $path2 = "C:\\Windows\\SysWOW64" nocase
        $path3 = "C:\\Windows\\system.ini" nocase
        $path4 = "C:\\Windows\\win.ini" nocase
        $path5 = "C:\\boot.ini" nocase
    condition:
        any of them
}

rule Critical_Linux_System_Path
{
    meta:
        description = "Linux/Unix system path access"
        category = "critical"
        score = 50
        severity = "linux"
    strings:
        $path1 = "/etc/passwd"
        $path2 = "/etc/shadow"
        $path3 = "/etc/sudoers"
        $path4 = "/etc/hosts"
        $path5 = "/root/"
        $path6 = "/proc/"
        $path7 = "/sys/"
        $path8 = "/boot/"
        $path9 = "/var/log/"
    condition:
        any of them
}

rule Critical_Mac_System_Path
{
    meta:
        description = "macOS system path access"
        category = "critical"
        score = 50
        severity = "mac"
    strings:
        $path1 = "/Library/Preferences/"
        $path2 = "/System/Library/"
        $path3 = "/private/var/"
        $path4 = "/private/etc/"
    condition:
        any of them
}

rule Critical_Credentials_Path
{
    meta:
        description = "SSH/Cloud credentials path access"
        category = "critical"
        score = 50
        severity = "credentials"
    strings:
        $ssh1 = ".ssh/id_rsa"
        $ssh2 = ".ssh/id_dsa"
        $ssh3 = ".ssh/id_ecdsa"
        $ssh4 = ".ssh/id_ed25519"
        $ssh5 = ".ssh/authorized_keys"
        $ssh6 = ".ssh/known_hosts"
        $aws = ".aws/credentials"
        $azure = ".azure/"
        $kube = ".kube/config"
        $docker = ".docker/config.json"
    condition:
        any of them
}

// ========== System Keywords ==========

rule System_Keyword_Critical
{
    meta:
        description = "Critical system directory keywords"
        category = "critical"
        score = 40
    strings:
        $kw1 = "system32" nocase
        $kw2 = "syswow64" nocase
        $kw3 = "etc/passwd" nocase
        $kw4 = "etc/shadow" nocase
        $kw5 = ".ssh/" nocase
        $kw6 = ".aws/" nocase
        $kw7 = ".azure/" nocase
        $kw8 = ".kube/" nocase
    condition:
        any of them
}

rule System_Keyword_High
{
    meta:
        description = "High-risk system directory keywords"
        category = "high"
        score = 30
    strings:
        $kw1 = "windows" nocase
        $kw2 = "program files" nocase
        $kw3 = "programdata" nocase
        $kw4 = "appdata" nocase
        $kw5 = "/etc/" nocase
        $kw6 = "/root/" nocase
        $kw7 = "/proc/" nocase
        $kw8 = "/sys/" nocase
        $kw9 = "/boot/" nocase
        $kw10 = "/var/log/" nocase
        $kw11 = "/usr/bin/" nocase
        $kw12 = "/usr/sbin/" nocase
        $kw13 = "library/preferences" nocase
        $kw14 = "system/library" nocase
    condition:
        any of them
}

rule System_Keyword_Medium
{
    meta:
        description = "Medium-risk system directory keywords"
        category = "medium"
        score = 20
    strings:
        $kw1 = "users/" nocase
        $kw2 = "home/" nocase
        $kw3 = "documents/" nocase
        $kw4 = "desktop/" nocase
        $kw5 = "/tmp/" nocase
        $kw6 = "/var/" nocase
        $kw7 = "/opt/" nocase
        $kw8 = "/usr/" nocase
        $kw9 = "local/" nocase
        $kw10 = "roaming/" nocase
    condition:
        any of them
}

// ========== Dangerous Extensions ==========

rule Dangerous_Extension_Critical
{
    meta:
        description = "Critical dangerous file extensions (keys/certificates)"
        category = "critical"
        score = 55
    strings:
        $ext1 = ".pem" nocase
        $ext2 = ".key" nocase
        $ext3 = ".crt" nocase
        $ext4 = ".pfx" nocase
        $ext5 = ".p12" nocase
        $ext6 = ".keystore" nocase
        $ext7 = ".jks" nocase
        $ext8 = ".der" nocase
        $ext9 = "id_rsa"
        $ext10 = "id_dsa"
        $ext11 = "id_ecdsa"
        $ext12 = "id_ed25519"
    condition:
        any of them
}

rule Dangerous_Extension_High
{
    meta:
        description = "High-risk dangerous file extensions (config/secrets)"
        category = "high"
        score = 35
    strings:
        $ext1 = ".env" nocase
        $ext2 = ".htpasswd" nocase
        $ext3 = ".htaccess" nocase
        $ext4 = ".bashrc" nocase
        $ext5 = ".bash_profile" nocase
        $ext6 = ".zshrc" nocase
        $ext7 = ".npmrc" nocase
        $ext8 = ".pypirc" nocase
        $ext9 = ".netrc" nocase
        $ext10 = ".gitconfig" nocase
        $ext11 = ".git-credentials" nocase
        $ext12 = "credentials" nocase
        $ext13 = "secrets" nocase
    condition:
        any of them
}

rule Dangerous_Extension_Medium
{
    meta:
        description = "Medium-risk file extensions (config/backup)"
        category = "medium"
        score = 15
    strings:
        $ext1 = ".conf" nocase
        $ext2 = ".config" nocase
        $ext3 = ".ini" nocase
        $ext4 = ".cfg" nocase
        $ext5 = ".yaml" nocase
        $ext6 = ".yml" nocase
        $ext7 = ".json" nocase
        $ext8 = ".xml" nocase
        $ext9 = ".log" nocase
        $ext10 = ".bak" nocase
        $ext11 = ".old" nocase
        $ext12 = ".backup" nocase
    condition:
        any of them
}

// ========== Path Traversal ==========

rule Path_Traversal_Simple
{
    meta:
        description = "Parent directory traversal"
        category = "high"
        score = 30
        reason = "Parent directory traversal"
    strings:
        $trav1 = /\.\.[\\/]/
    condition:
        $trav1
}

rule Path_Traversal_URL_Encoded
{
    meta:
        description = "URL encoded path traversal"
        category = "high"
        score = 35
        reason = "URL encoded traversal"
    strings:
        $trav1 = /%2e%2e%2f/ nocase
        $trav2 = /%2e%2e\// nocase
        $trav3 = /\.\.%2f/ nocase
    condition:
        any of them
}

rule Path_Traversal_Double_Encoded
{
    meta:
        description = "Double URL encoded path traversal"
        category = "critical"
        score = 40
        reason = "Double URL encoded traversal"
    strings:
        $trav1 = /%252e%252e%252f/ nocase
        $trav2 = /\.\.%255c/ nocase
    condition:
        any of them
}
