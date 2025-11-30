# shell.nix - used with nix-shell to get a development environment with necessary dependencies
# Should be enough to run unit tests, integration tests and the service won't work
# If you don't use nix, don't worry about/use this file
let
  pkgs = import <nixpkgs> { };
  python = pkgs.python310;
in
pkgs.mkShell {
  nativeBuildInputs = [
    pkgs.pkg-config
    pkgs.wrapGAppsHook
  ];
  buildInputs = [
    pkgs.gobject-introspection
    pkgs.gtk3
    pkgs.bashInteractive
    pkgs.gobject-introspection
    pkgs.xlibs.xmodmap
    pkgs.gtksourceview4
    (python.withPackages (
      python-packages: with python-packages; [
        pip
        wheel

        evdev
        dasbus
        pygobject3
        pydantic

        psutil # only used in tests
      ]
    ))
  ];
  # https://nixos.wiki/wiki/Python#Emulating_virtualenv_with_nix-shell
  shellHook = ''
    # Tells pip to put packages into $PIP_PREFIX instead of the usual locations.
    # See https://pip.pypa.io/en/stable/user_guide/#environment-variables.
    export PIP_PREFIX=$(pwd)/venv
    export PYTHONPATH="$PIP_PREFIX/${python.sitePackages}:$PYTHONPATH"
    export PATH="$PIP_PREFIX/bin:$PATH"
    unset SOURCE_DATE_EPOCH

    python setup.py egg_info
    pip install `grep -v '^\[' *.egg-info/requires.txt` || true
  '';
}
