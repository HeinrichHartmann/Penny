{
  description = "Penny - Personal finance tracking and analysis";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        playwrightBrowsers = pkgs.playwright-driver.browsers;
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Python
            python311

            # Package management
            uv
            nodejs_22
            playwright-driver

            # For briefcase / native app building
            # macOS-specific dependencies handled by briefcase
          ] ++ pkgs.lib.optionals pkgs.stdenv.isLinux [
            # Linux specific (for tkinter)
            tk
            tcl
          ];

          shellHook = ''
            export PLAYWRIGHT_BROWSERS_PATH="${playwrightBrowsers}"
            export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

            echo "Penny development environment"
            echo "Python: $(python --version)"
            echo "UV: $(uv --version)"
            echo "Node: $(node --version)"
            echo "npm: $(npm --version)"
            echo "Playwright browsers: $PLAYWRIGHT_BROWSERS_PATH"
            echo ""
            echo "Commands:"
            echo "  make frontend-build - Build bundled frontend assets"
            echo "  make dev    - Run development server"
            echo "  make test-ui - Run Playwright UI tests"
            echo "  make app    - Build macOS app"
            echo ""
          '';
        };
      }
    );
}
