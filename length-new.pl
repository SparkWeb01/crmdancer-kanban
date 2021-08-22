#!/usr/bin/env perl 
#===============================================================================
#
#         FILE: length.pl
#
#        USAGE: ./length.pl
#
#  DESCRIPTION: Узнаем время звучания  mp3-файла и сохраняем в csv файл.
#  				Для каждого дня свой csv-файл.
#
#      OPTIONS: ---
# REQUIREMENTS: ---
#         BUGS: ---
#        NOTES: ---
#       AUTHOR: YOUR NAME (),
# ORGANIZATION:
#      VERSION: 1.0
#      CREATED: 27.06.2015 08:38:21
#     REVISION: ---
#===============================================================================
use strict;
use warnings;
use utf8;
use File::Find::Rule;
use File::Basename;
use POSIX 'strftime';
use Data::Dumper;
use File::Slurp;

my $today = strftime '%Y%m%d', localtime;

my @files =
  File::Find::Rule->file()->name( '*-' . $today . '-*.mp3' )
  ->in('/home/w2/thewire/media/mp3');

my @data;
for my $path (@files) {

    my $length =
      `/bin/mp3info -x $path 2>&1|/bin/grep 'Length:'|/bin/sed 's/Length://'`;
    $length =~ s/^\s+|\s+$//g;
    my ( $filename, undef, undef ) = fileparse( $path, qr/\.[^.]*/ );
    push( @data, "$filename, $length\n" );
}

if (@data) {
    my $filename = '/home/w2/thewire/media/mp3/' . $today . '.csv';
    write_file( $filename, @data );
}
