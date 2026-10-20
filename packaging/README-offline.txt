Rime Ice Settings offline bundle for Ubuntu 24.04 amd64

Extract the archive on the destination computer, then run:

    cd bundle
    sudo ./install-offline.sh

The installer verifies FULL_SHA256SUMS and SHA256SUMS, prints an APT transaction preview, and asks
for confirmation. Use --yes to accept the preview without an interactive prompt.
APT uses only the bundle's local file repository and --no-download, so it cannot
fetch packages from the network. It requests only rime-ice-settings; installed
newer dependencies may satisfy its requirements. APT rejects package removal
and downgrades. If the target has an incompatible package set, installation
stops; it does not alter the APT sources or configuration on the target.

The archive contains the application package and the dependency closure selected
from the authenticated Ubuntu 24.04 main/universe, updates, and security indexes
at bundle creation time. PACKAGES.tsv records the exact package versions and
source package names; SHA256SUMS records the payload hashes. Keep these files
with the packages. Individual Ubuntu packages include their copyright notices
under /usr/share/doc after installation.

source/rime-ice-settings_0.1.0_source.tar.gz contains the exact application,
Rime data, and packaging source snapshot. Ubuntu dependency source packages are
not included in this runtime archive; the builder's build_sources.sh command
can collect them as a separate archive for redistribution alongside it.

The included Rime Ice configuration is installed as a read-only system snapshot.
The settings application activates it for each user on first use. Installing
this bundle does not directly edit a user's home directory.
