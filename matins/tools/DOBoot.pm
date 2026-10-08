package DOBoot;
# Boot the Divinum Officium engine (web/cgi-bin/horas/officium.pl) for one
# date's Matins, unchanged except that print_content() — which would render
# HTML — is replaced by a callback. Inside the callback every engine global
# (%winner, $rule, $commune, ...) and function (lectio, setupstring, ...) is
# set up exactly as it would be for the real page.
#
#   use DOBoot;
#   DOBoot::run_matins('11-04-2026', 'Divino Afflatu - 1954', sub {
#     my ($lang1, $script1, $lang2, $script2) = @_;
#     ...
#   });
#
# One call per process: officium.pl keeps its state in package globals.
use strict;
use warnings;
no warnings 'once';
use FindBin;
use Cwd qw(abs_path);
use File::Basename qw(dirname);

our $ENGINE = abs_path(dirname(__FILE__) . '/../../web/cgi-bin/horas');

sub run_matins {
  my ($date, $version, $callback) = @_;
  my $engine = $ENGINE;

  # officium.pl does `use FindBin qw($Bin)` and requires "$Bin/...". Point $Bin
  # at the engine so those requires resolve, and pre-load webdia.pl under the
  # same path so our print_content survives officium.pl's own require.
  $FindBin::Bin = $engine;
  unshift @INC, "$engine/..";
  {
    package main;
    no strict;
    no warnings;
    require "$engine/webdia.pl";
  }
  {
    no warnings 'redefine';
    *main::print_content = $callback;
  }

  # Silence the HTML the rest of officium.pl prints; hand back the real STDOUT.
  open(my $out, '>&', \*STDOUT) or die;
  open(STDOUT, '>', '/dev/null') or die;
  {
    package main;
    local $0 = "$engine/officium.pl";
    local @ARGV = ("version=$version", 'command=prayMatutinum', "date=$date", 'lang1=Latin', 'lang2=English');
    no strict;
    no warnings;
    do "$engine/officium.pl";
    die $@ if $@;
  }
  binmode($out, ':raw');
  return $out;
}

1;
