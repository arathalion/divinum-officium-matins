#!/usr/bin/perl
# harvest_day.pl — run the Divinum Officium engine for one date and dump the
# Matins lessons and responsories (Latin + English) as one line of JSON
# (PRETTY=1 for indented output).
#
# Usage: perl matins/tools/harvest_day.pl MM-DD-YYYY [version] [language]
#   language: a folder of web/www/horas (English, Italiano, Espanol, ...); the
#   translation is returned as "english" for English and "vernacular" always.
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

my ($date, $version, $lang2) = @ARGV;
die "usage: $0 MM-DD-YYYY [version] [language]\n" unless $date && $date =~ /^\d\d-\d\d-\d{4}$/;
$version ||= 'Divino Afflatu - 1954';
$lang2 ||= 'English';

my %result = (date => $date, version => $version, language => $lang2, lessons => []);

my $out = DOBoot::run_matins(
  $date, $version,
  sub {
    my ($lang1, $script1, $lang2, $script2) = @_;
    my @seen;

    for my $line (@$script1) {
      push @seen, $1 while ($line // '') =~ /\&lectio\((\d+)\)/g;
    }

    # Monastic offices with one lesson written into the script itself rather
    # than produced by lectio(): "#Lectio brevis" (summer ferias: the text
    # follows the heading in the same item) and "#Lectio unica" (the text, Tu
    # autem and responsory follow as separate items).
    my $gather = sub {
      my ($script, $i) = @_;
      my $first = $script->[$i] =~ s/^#Lectio \w+[^\n]*\n?//r;
      return $first if $first =~ /\S/;
      my @parts;
      for my $j ($i + 1 .. $#$script) {
        my $item = $script->[$j] // '';
        last if $item =~ /^[#!](?!!)/ && $item !~ /^![^N]/;   # next heading or nocturn
        push @parts, $item;
        last if $item =~ /^R\.(?:br\.)? /;                   # responsory ends the lesson
      }
      return join("\n", @parts);
    };
    for my $i (0 .. $#$script1) {
      next unless ($script1->[$i] // '') =~ /^#Lectio (brevis|unica)/;
      my $kind = $1;
      my $la = $gather->($script1, $i);
      my $en = ($script2 && defined $script2->[$i] && $script2->[$i] =~ /^#Lectio/) ? $gather->($script2, $i) : $la;
      my %l = (n => 1, kind => $kind, latin => $la, vernacular => $en);
      $l{english} = $en if $lang2 eq 'English';
      push @{ $result{lessons} }, \%l;
    }

    for my $n (@seen) {
      local $main::column = 1;
      my $la = main::lectio($n, $lang1);
      $main::column = 2;
      my $en = main::lectio($n, $lang2);
      my %l = (n => 0 + $n, latin => $la, vernacular => $en);
      $l{english} = $en if $lang2 eq 'English';
      push @{ $result{lessons} }, \%l;
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
    $result{rank_field} = $main::winner{Rank};    # "Title;;Duplex;;3;;vide C4"

    # Offices commemorated today, with their titles in Latin and the vernacular.
    my $title = sub {
      my $h = shift;
      return '' unless $h && ref $h eq 'HASH';
      return $h->{Officium} if $h->{Officium};
      return (split /;;/, ($h->{Rank} // ''))[0] // '';
    };
    my (%seen, @comm);
    for my $f (grep { defined && length } ($main::commemoratio, @main::commemoentries)) {
      my $file = $f =~ /\.txt$/ ? $f : "$f.txt";
      next if $file eq ($main::winner // '') || $seen{$file}++;
      my $la = $title->(main::setupstring('Latin', $file));
      next unless $la;
      push @comm, { file => $file, latin => $la, local => $title->(main::setupstring($lang2, $file)) };
    }
    $result{commemorations} = \@comm;
    $result{commemoentries} = [@main::commemoentries];
    $result{build} = $main::buildscript;
  },
  $lang2
);

my $pretty = $ENV{PRETTY} ? 1 : 0;
print $out JSON::PP->new->utf8->canonical->pretty($pretty)->encode(\%result), ($pretty ? '' : "\n");
