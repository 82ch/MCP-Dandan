#!/usr/bin/env python3
"""
Install SSL certificates for Python on macOS.
This should be run once after installation.
"""

import os
import platform
import ssl
import stat
import sys


def install_certificates():
    """Install certifi certificates for Python SSL."""
    try:
        import certifi
    except ImportError:
        print("Installing certifi...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "certifi"])
        import certifi

    # Get OpenSSL paths
    openssl_dir, openssl_cafile = os.path.split(
        ssl.get_default_verify_paths().openssl_cafile
    )

    print(f"OpenSSL directory: {openssl_dir}")
    print(f"OpenSSL CA file: {openssl_cafile}")
    print(f"Certifi bundle: {certifi.where()}")

    # Check if already installed
    cert_path = os.path.join(openssl_dir, openssl_cafile)
    if os.path.exists(cert_path):
        if os.path.islink(cert_path):
            target = os.readlink(cert_path)
            print(f"✓ Certificate symlink already exists: {openssl_cafile} -> {target}")
            return True
        else:
            print(f"✓ Certificate file already exists: {cert_path}")
            return True

    # Create directory if it doesn't exist
    os.makedirs(openssl_dir, exist_ok=True)

    # Change to OpenSSL directory
    os.chdir(openssl_dir)
    relpath_to_certifi = os.path.relpath(certifi.where())

    print(f"Creating symlink: {openssl_cafile} -> {relpath_to_certifi}")

    # Remove existing file if present
    try:
        os.remove(openssl_cafile)
        print("Removed existing file")
    except FileNotFoundError:
        pass

    # Create symlink
    os.symlink(relpath_to_certifi, openssl_cafile)
    print("✓ Symlink created")

    # Set permissions (rwxrwxr-x)
    STAT_0o775 = (
        stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
        stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP |
        stat.S_IROTH | stat.S_IXOTH
    )
    os.chmod(openssl_cafile, STAT_0o775)
    print("✓ Permissions set")

    print("\n✓ Certificate installation complete!")
    return True


def main():
    system = platform.system()

    print(f"Platform: {system}")
    print(f"Python: {sys.version}")
    print()

    if system == "Darwin":  # macOS
        print("Detected macOS - installing certificates...")
        try:
            install_certificates()
        except PermissionError:
            print("\n✗ Permission denied. You may need to run with appropriate permissions.")
            print(f"  Try: sudo {sys.executable} {__file__}")
            return 1
        except Exception as e:
            print(f"\n✗ Installation failed: {e}")
            return 1
    elif system == "Linux":
        print("Linux detected - checking system CA bundle...")
        paths = ssl.get_default_verify_paths()
        if paths.cafile and os.path.exists(paths.cafile):
            print(f"✓ System CA bundle found: {paths.cafile}")
        else:
            print("Installing certifi as fallback...")
            try:
                install_certificates()
            except Exception as e:
                print(f"✗ Installation failed: {e}")
                return 1
    elif system == "Windows":
        print("Windows detected - certifi should work automatically")
        try:
            import certifi
            print(f"✓ Certifi is installed: {certifi.where()}")
        except ImportError:
            print("Installing certifi...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "certifi"])
    else:
        print(f"Unknown platform: {system}")
        print("Attempting to install certifi...")
        try:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "certifi"])
        except Exception as e:
            print(f"✗ Installation failed: {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
