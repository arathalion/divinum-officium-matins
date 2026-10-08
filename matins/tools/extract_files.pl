#!/usr/bin/perl
# extract_files.pl — print the Matins-related sections of office files, as the
# engine resolves them for one rubrical version (conditionals applied, @
# inclusions expanded, language layers merged), in Latin and English.
#
# Usage: perl matins/tools/extract_files.pl [version] < filelist > files.jsonl
#
# filelist: one path per line relative to web/www/horas/<Language>/, e.g.
# "Sancti/11-04.txt", "Tempora/Pent23-3.txt", "Commune/C4.txt".
# Output: one JSON object per file: {file, latin: {Section: text}, english: {...}}
use strict;
use warnings;
no warnings 'once';
use utf8;
use FindBin;
use lib $FindBin::Bin;
use JSON::PP;
use DOBoot;

my $version = shift || 'Divino Afflatu - 1954';
my @files = grep {/\S/} map { s/\s+$//r } <STDIN>;
my $json = JSON::PP->new->utf8->canonical;
my $wanted = qr/^(?:Officium|Rank|Rule|Lectio.*|Responsory.*|Benedictio.*|Nocturn.*|Invit|Commemoratio.*)$/;
my @rows;

# Any ordinary date will do: we only need the engine initialised for $version.
my $out = DOBoot::run_matins(
  '01-15-2026', $version,
  sub {
    for my $file (@files) {
      my %row = (file => $file);

      for my $lang (qw(Latin English)) {
        my $s = main::setupstring($lang, $file);
        my %sec;

        if ($s && ref $s eq 'HASH') {
          for my $k (keys %$s) {
            $sec{$k} = $s->{$k} if $k =~ $wanted;
          }
        }
        $row{ lc $lang } = \%sec;
      }
      push @rows, \%row;
    }
  }
);

print $out $json->encode($_), "\n" for @rows;
