# Maintainer: Taki <you@example.com>
pkgname=manjaro-task-manager
pkgver=1.0.0
pkgrel=1
pkgdesc="A modern, Manjaro-inspired Task Manager for Arch Linux and Arch-based distributions"
arch=('any')
url="https://github.com/Takiblu"
license=('GPL3')
depends=(
    'python'
    'python-pyside6'
    'python-psutil'
    'polkit'
    'systemd'
)
optdepends=(
    'wmctrl: improved window-manager detection'
    'xdg-utils: "Open File Location" support'
    'libnotify: desktop notifications fallback via notify-send'
    'nvidia-utils: NVIDIA GPU monitoring via nvidia-smi'
    'python-xlib: native global shortcut support on X11'
    'gsettings-desktop-schemas: global shortcut registration on GNOME/Wayland'
)
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-hatchling')
source=("$pkgname-$pkgver.tar.gz")
sha256sums=('SKIP')  # replace with the real checksum when publishing a release tarball
backup=()
install=

package() {
    cd "$srcdir/$pkgname-$pkgver"

    # Application source
    install -dm755 "$pkgdir/usr/lib/$pkgname"
    cp -r src "$pkgdir/usr/lib/$pkgname/src"

    # Launcher script
    install -dm755 "$pkgdir/usr/bin"
    install -m755 packaging/manjaro-task-manager.sh "$pkgdir/usr/bin/manjaro-task-manager"

    # Desktop entry
    install -Dm644 packaging/manjaro-task-manager.desktop \
        "$pkgdir/usr/share/applications/manjaro-task-manager.desktop"

    # Icon
    install -Dm644 assets/icons/manjaro-task-manager.svg \
        "$pkgdir/usr/share/icons/hicolor/scalable/apps/manjaro-task-manager.svg"

    # Polkit policy (allows the desktop's polkit agent to prompt cleanly
    # for the small set of actions that genuinely need elevation)
    install -Dm644 packaging/org.manjarotaskmanager.policy \
        "$pkgdir/usr/share/polkit-1/actions/org.manjarotaskmanager.policy"

    # License
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"

    # systemd --user unit for optional "start with system" (installed but
    # not enabled by default; the app's own Settings > Startup toggle
    # enables it via `systemctl --user enable` at runtime, not here)
    install -Dm644 packaging/manjaro-task-manager.service \
        "$pkgdir/usr/lib/systemd/user/manjaro-task-manager.service"
}
