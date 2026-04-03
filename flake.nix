{
  description = "F4U - Finance For You development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Python
            python311

            # Package management
            uv

            # For briefcase / native app building
            # macOS-specific dependencies handled by briefcase
          ] ++ pkgs.lib.optionals pkgs.stdenv.isDarwin [
            # macOS specific
            darwin.apple_sdk.frameworks.Cocoa
            darwin.apple_sdk.frameworks.WebKit
          ] ++ pkgs.lib.optionals pkgs.stdenv.isLinux [
            # Linux specific (for tkinter)
            tk
            tcl
          ];

          shellHook = ''
            echo "F4U development environment"
            echo "Python: $(python --version)"
            echo "UV: $(uv --version)"
            echo ""
            echo "Commands:"
            echo "  make dev    - Run development server"
            echo "  make build  - Build macOS app"
            echo ""
          '';
        };
      }
    );
}
