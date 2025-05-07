{pkgs}: {
  deps = [
    pkgs.rustc
    pkgs.pkg-config
    pkgs.libiconv
    pkgs.cargo
    pkgs.zlib
    pkgs.tk
    pkgs.tcl
    pkgs.openjpeg
    pkgs.libxcrypt
    pkgs.libwebp
    pkgs.libtiff
    pkgs.libjpeg
    pkgs.libimagequant
    pkgs.lcms2
    pkgs.freetype
    pkgs.glibcLocales
    pkgs.postgresql
    pkgs.openssl
  ];
}
