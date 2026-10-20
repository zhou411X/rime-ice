Packaging Rime Ice

For the standard Debian release, after the public application sources and
data/rime snapshot are ready, run:

    ./build_deb.sh
    ./build_source.sh

These commands produce dist/rime-ice_0.2.0_all.deb, the empty
dist/rime-ice-settings_0.2.0_all.deb upgrade transition, and
dist/rime-ice_0.2.0_source.tar.gz. The .deb declares its Ubuntu dependencies;
users install those with APT. No Ubuntu binary packages are bundled.

The source archive contains public application code, reviewed Rime data,
themes and licenses, packaging scripts, tests, README.md, and the reviewed
settings screenshot. The data copy uses an explicit file type allowlist and
excludes user caches and private working files.

The offline dependency bundle is an optional, separately built artifact for
Ubuntu 24.04 amd64. It is not part of the standard release. To build it:

    ./build_offline.sh
    ./build_sources.sh

To reuse the verified 0.1.0 dependency bundle during an optional offline build:

    ./build_offline.sh --from-bundle dist/rime-ice-settings_0.1.0_ubuntu24.04_amd64_offline.tar.gz

After an application-only edit with unchanged Depends, rebuild both .debs and
use `./build_offline.sh --reuse-bundle` to refresh the optional runtime bundle.
An offline bundle downloads the authenticated Ubuntu dependency closure using
isolated APT state. The companion build_sources.sh collects Ubuntu source
packages separately for that optional binary redistribution.
