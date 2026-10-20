Packaging Rime Ice Settings

On an Ubuntu 24.04 amd64 build computer, after the application sources and
data/rime snapshot are ready:

    ./build_deb.sh
    ./build_offline.sh
    ./build_sources.sh

After an application-only edit that leaves its Depends field unchanged, rebuild
the .deb and use `./build_offline.sh --reuse-bundle` to refresh the runtime
archive from the verified previous archive without redownloading Ubuntu .debs.

The first command creates dist/rime-ice-settings_0.1.0_all.deb. The second
uses authenticated Ubuntu noble, noble-updates, and noble-security APT indexes
to download the transitive binary dependency closure into an archive. It uses
an empty dpkg status and isolated APT lists/cache, so the bundle does not
depend on packages already installed on the build computer. It does not install
packages or alter the computer's APT configuration. The third command collects
the matching Ubuntu source packages into a separate redistribution archive.
Both archive builders need network access and enough free space.

The application package contains the Python GTK4 files, the public Rime Ice
snapshot, themes, icon, desktop entry, and README. The offline archive also
contains a SHA256 manifest and exact binary package inventory. It targets
Ubuntu 24.04 amd64 only. arm64 and other releases require a separately built
and tested dependency set.

Each Ubuntu binary .deb ships its corresponding copyright notices. Ubuntu
source packages are separate from the runtime archive; distribute the sources
archive alongside it when sharing the bundle. The source collector requires
the exact source versions still to be present on Ubuntu mirrors. PACKAGES.tsv
records the binary and source package versions.
