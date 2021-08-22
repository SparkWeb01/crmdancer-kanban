#!/usr/bin/env perl 
#===============================================================================
#
#         FILE: amievent.pl
#
#        USAGE: ./amievent.pl
#
#  DESCRIPTION: Скрипт наблюдает за входящими звонками и пишет их в базу и
#  				memcahed
#      OPTIONS: ---
# REQUIREMENTS: ---
#         BUGS: ---
#        NOTES: ---
#       AUTHOR: YOUR NAME (),
# ORGANIZATION:
#      VERSION: 1.0
#      CREATED: 05.12.2016 15:35:49
#     REVISION: ---
#===============================================================================

use strict;
use warnings;
use utf8;
use EV;
use Asterisk::AMI;
use Data::Dumper;
use feature 'say';
use POSIX qw(strftime);
use DBI;
use Cache::Memcached;

my $cache = new Cache::Memcached( { servers => ["127.0.0.1:11211"], debug => 0 } );

#Create your connection
my $astman = Asterisk::AMI->new(
    PeerAddr       => 'f1.ats.com',
    PeerPort       => '5038',
    Username       => 'login',
    Secret         => 'pass',
    Events         => 'on',
    Blocking       => 0,
    Keepalive      => 60,
    on_connect_err => sub { say 'Error connect'; exit; },
    on_error       => sub { say 'Error occured on socket'; exit; },
    on_timeout     => sub { say 'Connection to asterisk timed out'; exit; },
    on_disconnect  => sub { say 'Remote disconect'; exit; },
    Handlers => { default => \&eventhandler }
);

#Alternatively you can set Blocking => 0, and set an on_error sub to catch connection errors
#die "Unable to connect to asterisk" unless ($astman);

#Define the subroutines for events
sub eventhandler {
    my ( $ami, $event ) = @_;
    my $from = $event->{'ConnectedLineNum'};
    my $to   = $event->{'CallerIDNum'};

    #-------------------------------------------------------------------------------
    # С помощью этих условий получаем только входящие внешние звонки
    #-------------------------------------------------------------------------------

    if (    $event->{'Event'} eq 'Newstate'
        and $event->{'ChannelStateDesc'} eq 'Ringing'
        and $event->{'ConnectedLineName'} ne 'crmdancer'
	#and $event->{'Channel'} !~ m/queue/i
        and length($from) > 9
        and length($to) == 3 )
    {

		###  say 'DEBUG: ', Dumper($event);

        #-------------------------------------------------------------------------------
        #  Отсекаем дубликаты с memcached, т. к. 'Ringing' пока не возьмут трубку
        #-------------------------------------------------------------------------------

        my $check_key = 'in' . $from . $to;
        unless ( $cache->get($check_key) ) {
            $cache->set( $check_key, 1, 60 );
            $from =~ s/[^0-9]//gi;
            $to =~ s/[^0-9]//gi;
            my $user_id = $to;
            my $dbh = DBI->connect( 'dbi:mysql:dbname=crmdb;host=localhost', 'crmdb', 'habrhabr' ) or die 'Error connecting to database';
            $dbh->do('set names utf8');

			#-------------------------------------------------------------------------------
			#  Вычисляем в базе клиента с таким вх. номером
			#-------------------------------------------------------------------------------
			
            my $sql = qq{select a.client_id, a.contact_person, b.company_name from 
					contacts a, clients b where instr(reverse(a.tel), reverse(?)) = 1 
					and b.user_id = ? and a.client_id = b.id LIMIT 0,1};
            my ( $client_id, $contact_person, $company_name ) = $dbh->selectrow_array( $sql, undef, substr( $from, -7 ), $user_id );


			#-------------------------------------------------------------------------------
			#  Если клиент найден, то пишем в mysql и в memcached для flask и js
			#-------------------------------------------------------------------------------

            if ($client_id) {
                $contact_person =~ s/"/ /g;
                $company_name =~ s/"/ /g;
                my $val = qq({"client_id": "$client_id", "contact_person": "$contact_person", "company_name": "$company_name"});
                my $key = 'flask_cache_incall:' . $user_id;
                $cache->set( $key, $val, 60 );
            	my $call_time = strftime( "%Y-%m-%d %H:%M:%S", localtime( $event->{'Uniqueid'} ) );
                $sql = q{insert into  call_history ( user_id, client_id, incomming ,date_call, call_from, call_to ) 
					values (?, ?, ?, ?, ?, ?)};
                $dbh->do( $sql, undef, $user_id, $client_id, 1, $call_time, $from, $to );
            }

            $dbh->disconnect;
        }

    }
}

#Define a subroutine for your action callback
sub actioncb {
    my ( $ami, $response ) = @_;
    say 'Got Action Reponse: ', $response->{'Response'};
}

#Send an action
my $action = $astman->send_action( { Action => 'Ping' }, \&actioncb );

#Do all of you other eventy stuff here, or before all this stuff, whichever ..............

#Start our loop
EV::loop

