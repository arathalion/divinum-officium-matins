#!/usr/bin/perl
# harvest_day.pl — run the Divinum Officium engine for one date and dump the
# Matins lessons and responsories (Latin + English) as one line of JSON
# (PRETTY=1 for indented output).
#
# Usage: perl matins/tools/harvest_day.pl MM-DD-YYYY [version]
#
# Each &lectio(N) call in the day's Matins script is handed to the engine's own
# lectio(), so all rubrical decisions (occurrence, commemorations, scripture of
# the day, contracted lessons) stay with the engine.
use strict;
use warnings;
no warnings 'once';
use utf8;
use FindBin;
use lib $FindBin::Bin;
use JSON::PP;
use DOBoot;

my ($date, $version) = @ARGV;
die "usage: $0 MM-DD-YYYY [version]\n" unless $date && $date =~ /^\d\d-\d\d-\d{4}$/;
$version ||= 'Divino Afflatu - 1954';

my %result = (date => $date, version => $version, lessons => []);

my $out = DOBoot::run_matins(
  $date, $version,
  sub {
    my ($lang1, $script1, $lang2, $script2) = @_;
    my @seen;

    for my $line (@$script1) {
      push @seen, $1 while $line =~ /\&lectio\((\d+)\)/g;
    }

    for my $n (@seen) {
      local $main::column = 1;
      my $la = main::lectio($n, $lang1);
      $main::column = 2;
      my $en = main::lectio($n, $lang2);
      push @{ $result{lessons} }, { n => 0 + $n, latin => $la, english => $en };
    }
    $result{winner} = $main::winner;
    $result{commemoratio} = $main::commemoratio;
    $result{scriptura} = $main::scriptura;
    $result{commune} = $main::commune;
    $result{rank} = $main::rank;
    $result{rule} = $main::rule;
    $result{dayname} = [@main::dayname];
    $result{title_latin} = $main::winner{Officium};
    $result{title_english} = $main::winner2{Officium};
    $result{commemoentries} = [@main::commemoentries];
    $result{build} = $main::buildscript;
  }
);

my $pretty = $ENV{PRETTY} ? 1 : 0;
print $out JSON::PP->new->utf8->canonical->pretty($pretty)->encode(\%result), ($pretty ? '' : "\n");
