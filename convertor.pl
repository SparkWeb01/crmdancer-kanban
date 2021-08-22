#!/usr/bin/env perl 
#===============================================================================
#
#         FILE: convertor.pl
#
#        USAGE: ./convertor.pl
#
#  DESCRIPTION: Конвертируем wav файлы  в mp3. С предварительной проверкой на
#  				существование, чтобы каждый раз не конвертить
#
#      OPTIONS: ---
# REQUIREMENTS: ---
#         BUGS: ---
#        NOTES: ---
#       AUTHOR: YOUR NAME (),
# ORGANIZATION:
#      VERSION: 1.0
#      CREATED: 24.06.2015 14:30:05
#     REVISION: ---
#===============================================================================

use strict;
use warnings;
use utf8;
use File::Find::Rule;
use File::Basename;

my @files =
  File::Find::Rule->file()->name('*.wav')->in('/home/crmdancer/thewire/media/wav');

for my $path (@files) {
    my ( $filename, $dir, $ext ) = fileparse( $path, qr/\.[^.]*/ );
    my $mp3 = '/home/crmdancer/thewire/media/mp3/' . $filename . '.mp3';
    unless ( -e $mp3 ) {
        system("/usr/local/bin/lame $path $mp3 --quiet");
    }

}
