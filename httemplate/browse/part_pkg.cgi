<% include( 'elements/browse.html',
                 'title'                 => 'Package Definitions',
                 'menubar'               => \@menubar,
                 'html_init'             => $html_init,
                 'html_form'             => $html_form,
                 'html_posttotal'        => $html_posttotal,
                 'name'                  => 'package definitions',
                 'disableable'           => 1,
                 'disabled_statuspos'    => 4,
                 'agent_virt'            => 1,
                 'agent_null_right'      => [ $edit, $edit_global ],
                 'agent_null_right_link' => $edit_global,
                 'agent_pos'             => 7, #5?
                 'query'                 => { 'select'    => $select,
                                              'table'     => 'part_pkg',
                                              'hashref'   => \%hash,
                                              'extra_sql' => $extra_sql,
                                              'order_by'  => "ORDER BY $orderby"
                                            },
                 'count_query'           => $count_query,
                 'header'                => \@header,
                 'fields'                => \@fields,
                 'links'                 => \@links,
                 'align'                 => $align,
                 'link_field'            => 'pkgpart',
                 'html_init'             => $html_init,
                 'html_foot'             => $html_foot,
             )
%>
<%def .style>
<STYLE TYPE="text/css">
  .taxproduct_desc {
    color: blue;
    text-decoration: underline dotted;
  }
</STYLE>
<SCRIPT TYPE="text/javascript">
$().ready(function() {
  $('.taxproduct_desc').tooltip({});
});
$(document).ready(function(){
    $(this).scrollTop(0);
});
</SCRIPT>
</%def>
<%init>

my $curuser = $FS::CurrentUser::CurrentUser;

my $edit        = 'Edit package definitions';
my $edit_global = 'Edit global package definitions';
my $acl_edit        = $curuser->access_right($edit);
my $acl_edit_global = $curuser->access_right($edit_global);
my $acl_config      = $curuser->access_right('Configuration'); #to edit services
                                                               #and agent types
                                                               #and bulk change
my $acl_edit_bulk   = $curuser->access_right('Bulk edit package definitions');

die "access denied"
  unless $acl_edit || $acl_edit_global;

my $conf = new FS::Conf;
my $taxclasses = $conf->exists('enable_taxclasses');
my $taxvendor = $conf->config('tax_data_vendor');
my $money_char = $conf->config('money_char') || '$';
my $disable_counts = $conf->exists('config-disable_counts') ? 1 : 0;

my $select = '*';
my $orderby = 'pkgpart';
my %hash = ();
my $extra_count = '';
my $family_pkgpart;

if ( $cgi->param('active') ) {
  $orderby = 'num_active DESC';
}

my @where = ();

#if ( $cgi->param('activeONLY') ) {
#  push @where, ' WHERE num_active > 0 '; #XXX doesn't affect count...
#}

if ( $cgi->param('recurring') ) {
  $hash{'freq'} = { op=>'!=', value=>'0' };
  $extra_count = " freq != '0' ";
}

my $classnum = '';
if ( $cgi->param('classnum') =~ /^(\d+)$/ ) {
  $classnum = $1;
  push @where, $classnum ? "classnum =  $classnum"
                         : "classnum IS NULL";
}
$cgi->delete('classnum');

if ( $cgi->param('pkgpartbatch') =~ /^([\w\/\-\:\. ]+)$/ ) {
  push @where, "pkgpartbatch = '$1' ";
}

if ( $cgi->param('missing_recur_fee') ) {
  push @where, "NOT EXISTS ( SELECT 1 FROM part_pkg_option
                               WHERE optionname = 'recur_fee'
                                 AND part_pkg_option.pkgpart = part_pkg.pkgpart
                                 AND CAST( optionvalue AS NUMERIC ) > 0
                           )";
}

if ( $cgi->param('ratenum') =~ /^(\d+)$/ ) {
  push @where, "EXISTS( SELECT 1 FROM part_pkg_option
                          WHERE optionname LIKE '%ratenum'
                            AND optionvalue = '$1'
                            AND part_pkg_option.pkgpart = part_pkg.pkgpart
                      )";
}

if ( $cgi->param('family') =~ /^(\d+)$/ ) {
  $family_pkgpart = $1;
  push @where, "family_pkgpart = $1";
  # Hiding disabled or one-time charges and limiting by classnum aren't 
  # very useful in this mode, so all links should still refer back to the 
  # non-family-limited display.
  $cgi->param('showdisabled', 1);
  $cgi->delete('family');
}

push @where, FS::part_pkg->curuser_pkgs_sql
  unless $acl_edit_global;

my $extra_sql = scalar(@where)
                ? ( scalar(keys %hash) ? ' AND ' : ' WHERE ' ).
                  join( 'AND ', @where)
                : '';

my $agentnums_sql = $curuser->agentnums_sql( 'table'=>'cust_main' );
my $count_cust_pkg = "
  SELECT COUNT(*) FROM cust_pkg LEFT JOIN cust_main USING ( custnum )
    WHERE cust_pkg.pkgpart = part_pkg.pkgpart
      AND $agentnums_sql
";
my $count_cust_pkg_cancel = "
  SELECT COUNT(*) FROM cust_pkg LEFT JOIN cust_main USING ( custnum )
    LEFT JOIN cust_pkg AS cust_pkg_next
      ON (cust_pkg.pkgnum = cust_pkg_next.change_pkgnum)
    WHERE cust_pkg.pkgpart = part_pkg.pkgpart
      AND $agentnums_sql
      AND cust_pkg.cancel IS NOT NULL AND cust_pkg.cancel != 0
";

unless ( $disable_counts ) {
  $select = "

    *,

    ( $count_cust_pkg
        AND ( setup IS NULL OR setup = 0 )
        AND ( cancel IS NULL OR cancel = 0 )
        AND ( susp IS NULL OR susp = 0 )
    ) AS num_not_yet_billed,

    ( $count_cust_pkg
        AND setup IS NOT NULL AND setup != 0
        AND ( cancel IS NULL OR cancel = 0 )
        AND ( susp IS NULL OR susp = 0 )
    ) AS num_active,

    ( $count_cust_pkg
        AND ( cancel IS NULL OR cancel = 0 )
        AND susp IS NOT NULL AND susp != 0
        AND setup IS NOT NULL AND setup != 0
    ) AS num_suspended,

    ( $count_cust_pkg
        AND ( cancel IS NULL OR cancel = 0 )
        AND susp IS NOT NULL AND susp != 0
        AND ( setup IS NULL OR setup = 0 )
    ) AS num_on_hold,

    ( $count_cust_pkg_cancel
        AND (cust_pkg_next.pkgnum IS NULL
            OR cust_pkg_next.pkgpart != cust_pkg.pkgpart)
    ) AS num_cancelled

  ";
}

# About the num_cancelled expression: packages that were changed, but 
# kept the same pkgpart, are considered "moved", not "canceled" (because
# this is the part_pkg UI).  We could show the count of those but it's 
# probably not interesting.

my $html_init = qq!
    One or more service definitions are grouped together into a package 
    definition and given pricing information.  Customers purchase packages
    rather than purchase services directly.<BR><BR>
    <FORM METHOD="GET" ACTION="${p}edit/part_pkg.cgi">
    <A HREF="${p}edit/part_pkg.cgi"><I>Add a new package definition</I></A>
    or
    !.include('/elements/select-part_pkg.html', 'element_name' => 'clone' ). qq!
    <INPUT TYPE="submit" VALUE="Clone existing package">
    </FORM>
    <BR><BR>
  !;
$html_init .= include('.style');

$cgi->param('dummy', 1);

my $filter_change =
  qq(\n<SCRIPT TYPE="text/javascript">\n).
  "function filter_change() {".
  "  window.location = '". $cgi->self_url.
       ";classnum=' + document.getElementById('classnum').options[document.getElementById('classnum').selectedIndex].value".
  "}".
  "\n</SCRIPT>\n";

#restore this so pagination works
$cgi->param('classnum', $classnum) if length($classnum);

#should hide this if there aren't any classes
my $html_posttotal =
  "$filter_change\n<BR>( show class: ".
  include('/elements/select-pkg_class.html',
            #'curr_value'    => $classnum,
            'value'         => $classnum, #insist on 0 :/
            'onchange'      => 'filter_change()',
            'pre_options'   => [ '-1' => 'all',
                                 '0'  => '(none)', ],
            'disable_empty' => 1,
         ).
  ' )';

my $recur_toggle = $cgi->param('recurring') ? 'show' : 'hide';
$cgi->param('recurring', $cgi->param('recurring') ^ 1 );

$html_posttotal .=
  '( <A HREF="'. $cgi->self_url.'">'. "$recur_toggle one-time charges</A> )";

$cgi->param('recurring', $cgi->param('recurring') ^ 1 ); #put it back

# ------

my $link = [ $p.'edit/part_pkg.cgi?', 'pkgpart' ];

my @header = ( '#', 'Package', 'Comment', 'Custom' );
my @fields = ( 'pkgpart', 'pkg', 'comment',
               sub{ '<B><FONT COLOR="#0000CC">'.$_[0]->custom.'</FONT></B>' }
             );
my $align = 'rllc';
my @links = ( $link, $link, '', '' );

unless ( 0 ) { #already showing only one class or something?
  push @header, 'Class';
  push @fields, sub { shift->classname || '(none)'; };
  $align .= 'l';
}

if ( $conf->exists('pkg-addon_classnum') ) {
  push @header, "Add'l order class";
  push @fields, sub { shift->addon_classname || '(none)'; };
  $align .= 'l';
}

tie my %plans, 'Tie::IxHash', %{ FS::part_pkg::plan_info() };

tie my %plan_labels, 'Tie::IxHash',
  map {  $_ => ( $plans{$_}->{'shortname'} || $plans{$_}->{'name'} ) }
      keys %plans;

push @header, 'Pricing';
$align .= 'r'; #?
push @fields, sub {
  my $part_pkg = shift;
  (my $plan = $plan_labels{$part_pkg->plan} ) =~ s/ /&nbsp;/g;
  my $is_recur = ( $part_pkg->freq ne '0' );
  my @discounts = sort { $a->months <=> $b->months }
                  map { $_->discount  }
                  $part_pkg->part_pkg_discount;

  [
    # Line 0: Family package link (if applicable)
    ( !$family_pkgpart &&
      $part_pkg->pkgpart == $part_pkg->family_pkgpart ? () : [
      {
        'align'=> 'center',
        'colspan' => 2,
        'size' => '-1',
        'data' => '<b>Show all versions</b>',
        'link' => $p.'browse/part_pkg.cgi?family='.$part_pkg->family_pkgpart,
      }
    ] ),
    [ # Line 1: Plan type (Anniversary, Prorate, Call Rating, etc.)
      { data =>$plan,
        align=>'center',
        colspan=>2,
      },
    ],
    [ # Line 2: Setup fee
      { data =>$money_char.
               sprintf('%.2f ', $part_pkg->option('setup_fee') ),
        align=>'right'
      },
      { data => ( ( $is_recur ? ' &nbsp; setup' : ' &nbsp; one-time' ).
                  ( $part_pkg->option('recur_fee') == 0
                      && $part_pkg->setup_show_zero
                    ? ' (printed on invoices)'
                    : ''
                  )
                ),
        align=>'left',
      },
    ],
    [ # Line 3: Recurring fee
      { data=>(
          $is_recur
            ? $money_char. sprintf('%.2f', $part_pkg->option('recur_fee'))
            : $part_pkg->freq_pretty
        ),
        align=> ( $is_recur ? 'right' : 'center' ),
        colspan=> ( $is_recur ? 1 : 2 ),
      },
      ( $is_recur
        ?  { data => ' &nbsp; '. $part_pkg->freq_pretty.
                     ( $part_pkg->option('recur_fee') == 0
                         && $part_pkg->recur_show_zero
                       ? ' (printed on invoices)'
                       : ''
                     ),
             align=>'left',
           }
        : ()
      ),
    ],
    [ { data => '&nbsp;' }, ], # Line 4: empty
    ( $part_pkg->adjourn_months ? 
      [ # Line 5: Adjourn months
        { data => mt('After [quant,_1,month], <strong>suspend</strong> the package.',
                     $part_pkg->adjourn_months),
          align => 'left',
          size  => -1,
          colspan => 2,
        }
      ] : ()
    ),
    ( $part_pkg->contract_end_months ? 
      [ # Line 6: Contract end months
        { data => mt('After [quant,_1,month], <strong>contract ends</strong>.',
                     $part_pkg->contract_end_months),
          align => 'left',
          size  => -1,
          colspan => 2,
        }
      ] : ()
    ),
    ( $part_pkg->expire_months ? 
      [ # Line 7: Expire months and automatic transfer
        { data => $part_pkg->change_to_pkgpart ?
                    mt('After [quant,_1,month], <strong>change to</strong> ',
                      $part_pkg->expire_months) .
                    qq(<a href="${p}edit/part_pkg.cgi?) .
                      $part_pkg->change_to_pkgpart .
                      qq(">) . $part_pkg->change_to_pkg->pkg . qq(</a>) . '.'
                  : mt('After [quant,_1,month], <strong>cancel</strong> the package.',
                     $part_pkg->expire_months)
          ,
          align => 'left',
          size  => -1,
          colspan => 2,
        }
      ] : ()
    ),
    ( # Usage prices
      map { my $amount = $_->amount / ($_->target_info->{multiplier} || 1);
            my $label = $_->target_info->{label};
            [
              { data    => "Plus&nbsp;$money_char". $_->price. '&nbsp;'.
                           ( $_->action eq 'increment' ? 'per' : 'for' ).
                           "&nbsp;$amount&nbsp;$label",
                align   => 'center', #left?
                colspan => 2,
              },
            ];
          }
        $part_pkg->part_pkg_usageprice
    ),
    ( # Supplementals
      map { my $dst_pkg = $_->dst_pkg;
            [
              { data => 'Supplemental: &nbsp;'.
                        '<A HREF="#'. $dst_pkg->pkgpart . '">' .
                        $dst_pkg->pkg . '</A>',
                align=> 'center',
                colspan => 2,
              }
            ]
          }
      $part_pkg->supp_part_pkg_link
    ),
    ( # Billing add-ons/bundle packages
      map { 
            my $dst_pkg = $_->dst_pkg;
            [ 
              { data => 'Add-on:&nbsp;'.$dst_pkg->pkg_comment,
                align=>'center', #?
                colspan=>2,
              }
            ]
          }
      $part_pkg->bill_part_pkg_link
    ),
    ( # Discounts available
      scalar(@discounts)
        ?  [ 
              { data => '<b>Discounts</b>',
                align=>'center', #?
                colspan=>2,
              }
            ]
        : ()  
    ),
    ( scalar(@discounts)
        ? map { 
            [ 
              { data  => $_->months. ':',
                align => 'right',
              },
              { data => $_->amount ? '$'. $_->amount : $_->percent. '%'
              }
            ]
          }
          @discounts
        : ()
    ),
  ]; # end of "middle column"

#  $plan_labels{$part_pkg->plan}.'<BR>'.
#    $money_char.sprintf('%.2f setup<BR>', $part_pkg->option('setup_fee') ).
#    ( $part_pkg->freq ne '0'
#      ? $money_char.sprintf('%.2f ', $part_pkg->option('recur_fee') )
#      : ''
#    ).
#    $part_pkg->freq_pretty; #.'<BR>'
};

push @header, 'Cost&nbsp;tracking';
$align .= 'r'; #?
push @fields, sub {
  my $part_pkg = shift;
  #(my $plan = $plan_labels{$part_pkg->plan} ) =~ s/ /&nbsp;/g;
  my $is_recur = ( $part_pkg->freq ne '0' );

  [
    [
      { data => '&nbsp;', # $plan,
        align=>'center',
        colspan=>2,
      },
    ],
    [
      { data =>$money_char.
               sprintf('%.2f ', $part_pkg->setup_cost ),
        align=>'right'
      },
      { data => ( $is_recur ? '&nbsp;setup' : '&nbsp;one-time' ),
        align=>'left',
      },
    ],
    [
      { data=>(
          $is_recur
            ? $money_char. sprintf('%.2f', $part_pkg->recur_cost)
            : '(no&nbsp;recurring)' #$part_pkg->freq_pretty
        ),
        align=> ( $is_recur ? 'right' : 'center' ),
        colspan=> ( $is_recur ? 1 : 2 ),
      },
      ( $is_recur
        ?  { data => ( $is_recur
                         ? '&nbsp;'. $part_pkg->freq_pretty
                         : ''
                     ),
             align=>'left',
           }
        : ()
      ),
    ],
  ];
};

###
# Agent goes here if displayed
###

#agent type
if ( $acl_edit_global ) {
  #really we just want a count, but this is fine unless someone has tons
  my @all_agent_types = map {$_->typenum}
                          qsearch('agent_type', { 'disabled'=>'' });
  if ( scalar(@all_agent_types) > 1 ) {
    push @header, 'Agent types';
    my $typelink = $p. 'edit/agent_type.cgi?';
    push @fields, sub { my $part_pkg = shift;
                        [
                          map { my $agent_type = $_->agent_type;
                                [ 
                                  { 'data'  => $agent_type->atype, #escape?
                                    'align' => 'left',
                                    'link'  => ( $acl_config
                                                   ? $typelink.
                                                     $agent_type->typenum
                                                   : ''
                                               ),
                                  },
                                ];
                              }
                              $part_pkg->type_pkgs
                        ];
                      };
    $align .= 'l';
  }
}

#if ( $cgi->param('active') ) {
  push @header, 'Customer<BR>packages';
  my %col = %{ FS::cust_pkg->statuscolors };
  my $cust_pkg_link = $p. 'search/cust_pkg.cgi?pkgpart=';
  push @fields, sub { my $part_pkg = shift;
                        [
                        map( {
                              my $magic = $_;
                              my $label = $_;
                              if ( $magic eq 'active' && $part_pkg->freq == 0 ) {
                                $magic = 'inactive';
                                #$label = 'one-time charge';
                                $label = 'charge';
                              }
                              $label= 'not yet billed' if $magic eq 'not_yet_billed';
                              $label= 'on hold' if $magic eq 'on_hold';
                          
                              [
                                {
                                 'data'  => '<B><FONT COLOR="#'. $col{$label}. '">'.
                                            $part_pkg->get("num_$_").
                                            '</FONT></B>',
                                 'align' => 'right',
                                },
                                {
                                 'data'  => $label.
                                              ( $part_pkg->get("num_$_") != 1
                                                && $label =~ /charge$/
                                                  ? 's'
                                                  : ''
                                              ),
                                 'align' => 'left',
                                 'link'  => ( $part_pkg->get("num_$_") || $disable_counts
                                                ? $cust_pkg_link.
                                                  $part_pkg->pkgpart.
                                                  ";magic=$magic"
                                                : ''
                                            ),
                                },
                              ],
                            } (qw( on_hold not_yet_billed active suspended cancelled ))
                          ),
                      ($acl_config ? 
                        [ {}, 
                          { 'data'  => '<FONT SIZE="-1">[ '.
                              include('/elements/popup_link.html',
                                'label'       => 'change',
                                'action'      => "${p}edit/bulk-cust_pkg.html?".
                                                 'pkgpart='.$part_pkg->pkgpart,
                                'actionlabel' => 'Change Packages',
                                'width'       => 960,
                                'height'      => 210,
                              ).' ]</FONT>',
                            'align' => 'left',
                          } 
                        ] : () ),
                      ]; 
  };
  $align .= 'r';
#}

if ( $taxclasses ) {
  push @header, 'Taxclass';
  push @fields, sub { shift->taxclass() || '&nbsp;'; };
  $align .= 'l';
} elsif ( $taxvendor ) {
  push @header, 'Tax product';
  my @classnums = ( 'setup', 'recur' );
  my @classnames = ( 'Setup', 'Recur' );
  foreach ( qsearch('usage_class', { disabled => '' }) ) {
    push @classnums, $_->classnum;
    push @classnames, $_->classname;
  }
  my $taxproduct_sub = sub {
    my $ppt = shift;
    '<SPAN CLASS="taxproduct_desc" TITLE="' .
      encode_entities($ppt->description) .
    '">' . encode_entities($ppt->taxproduct) . '</SPAN>'
  };
  my $taxproduct_list_sub = sub {
    my $part_pkg = shift;
    my $base_ppt = $part_pkg->taxproduct;
    my $out = [];
    if ( $base_ppt ) {
      push @$out, [
        { 'data'  => '', 'align' => 'left' },
        { 'data'  => &$taxproduct_sub($base_ppt), 'align' => 'right' },
      ];
    }
    if ( my $units_ppt = $part_pkg->units_taxproduct ) {
      push @$out, [
        { 'data'  => emt('Lines'), 'align' => 'left' },
        { 'data'  => &$taxproduct_sub($units_ppt), 'align' => 'right' },
      ];
    }
    for (my $i = 0; $i < scalar @classnums; $i++) {
      my $num = $part_pkg->option('usage_taxproductnum_' . $classnums[$i]);
      next if !$num;
      my $ppt = FS::part_pkg_taxproduct->by_key($num);
      push @$out, [
        { 'data'  => $classnames[$i], 'align' => 'left', },
        { 'data'  => &$taxproduct_sub($ppt), 'align' => 'right' },
      ];
    }
    $out;
  };
  push @fields, $taxproduct_list_sub;
  $align .= 'l';
}

# make a table of report class optionnames =>  the actual 
my %report_optionname_name = map { 'report_option_'.$_->num, $_->name }
  qsearch('part_pkg_report_option', { disabled => '' });

push @header, 'Plan options',
              'Services';
              #'Service', 'Quan', 'Primary';

push @fields, 
              sub {
                    my $part_pkg = shift;
                    if ( $part_pkg->plan ) {

                      my %options = $part_pkg->options;
                      # gather any options that are really report options,
                      # convert them to their user-friendly names,
                      # and sort them (I think?)
                      my @report_options =
                        sort { $a cmp $b }
                        map { $report_optionname_name{$_} }
                        grep { $options{$_}
                               and exists($report_optionname_name{$_}) }
                        keys %options;

                      my @rows = (
                        map { 
                              [
                                { 'data'  => "$_: ",
                                  'align' => 'right',
                                },
                                { 'data'  => $part_pkg->format($_,$options{$_}),
                                  'align' => 'left',
                                },
                              ];
                            }
                        sort
                        grep { $options{$_} =~ /\S/ } 
                        grep { $_ !~ /^(setup|recur)_fee$/ 
                               and $_ !~ /^report_option_\d+$/
                               and $_ !~ /^usage_taxproductnum_/
                             }
                        keys %options
                      );
                      if ( @report_options ) {
                        push @rows,
                          [ { 'data'  => 'Report classes',
                              'align' => 'center',
                              'style' => 'font-weight: bold',
                              'colspan' => 2
                            } ];
                        foreach (@report_options) {
                          push @rows, [
                            { 'data'  => $_,
                              'align' => 'center',
                              'colspan' => 2
                            }
                          ];
                        } # foreach @report_options
                      } # if @report_options

                      return \@rows;

                    } else { # should never happen...

                      [ map { [
                                { 'data'  => uc($_),
                                  'align' => 'right',
                                },
                                {
                                  'data'  => $part_pkg->$_(),
                                  'align' => 'left',
                                },
                              ];
                            }
                        (qw(setup recur))
                      ];

                    }

                  },

              sub {
                    my $part_pkg = shift;
                    my @part_pkg_usage = sort { $a->priority <=> $b->priority }
                                         $part_pkg->part_pkg_usage;

                    [ 
                      (map {
                             my $pkg_svc = $_;
                             my $part_svc = $pkg_svc->part_svc;
                             my $svc = $part_svc->svc;
                             if ( $pkg_svc->primary_svc =~ /^Y/i ) {
                               $svc = "<B>$svc (PRIMARY)</B>";
                             }
                             $svc =~ s/ +/&nbsp;/g;

                             [
                               {
                                 'data'  => '<B>'. $pkg_svc->quantity. '</B>',
                                 'align' => 'right'
                               },
                               {
                                 'data'  => $svc,
                                 'align' => 'left',
                                 'link'  => ( $acl_config
                                                ? $p. 'edit/part_svc.cgi?'.
                                                  $part_svc->svcpart
                                                : ''
                                            ),
                               },
                             ];
                           }
                      sort {     $b->primary_svc =~ /^Y/i
                             <=> $a->primary_svc =~ /^Y/i
                           }
                           $part_pkg->pkg_svc('disable_linked'=>1)
                      ),
                      ( map { 
                              my $dst_pkg = $_->dst_pkg;
                              [
                                { data => 'Add-on:&nbsp;'.$dst_pkg->pkg_comment,
                                  align=>'center', #?
                                  colspan=>2,
                                }
                              ]
                            }
                        $part_pkg->svc_part_pkg_link
                      ),
                      ( scalar(@part_pkg_usage) ? 
                          [ { data  => 'Usage minutes',
                              align => 'center',
                              colspan    => 2,
                              data_style => 'b',
                              link  => $p.'browse/part_pkg_usage.html#pkgpart'.
                                       $part_pkg->pkgpart 
                            } ]
                          : ()
                      ),
                      ( map {
                              [ { data  => $_->minutes,
                                  align => 'right'
                                },
                                { data  => $_->description,
                                  align => 'left'
                                },
                              ]
                            } @part_pkg_usage
                      ),
                    ];

                  };

$align .= 'lrl'; #rr';

# --------

my $count_extra_sql = $extra_sql;
$count_extra_sql =~ s/^\s*AND /WHERE /i;
$extra_count = ( $count_extra_sql ? ' AND ' : ' WHERE ' ). $extra_count
  if $extra_count;
my $count_query = "SELECT COUNT(*) FROM part_pkg $count_extra_sql $extra_count";

my $html_form = '';
my $html_foot = '';
if ( $acl_edit_bulk ) {
  # insert a checkbox column
  push @header, '';
  push @fields, sub {
    '<INPUT TYPE="checkbox" NAME="pkgpart" VALUE=' . $_[0]->pkgpart .'>';
  };
  push @links, '';
  $align .= 'c';
  $html_form = qq!<FORM ACTION="${p}edit/bulk-part_pkg.html" METHOD="POST">!;
  $html_foot = include('/search/elements/checkbox-foot.html',
                 actions => [
                   { label  => 'edit packages',
                     onclick=> include('/elements/popup_link_onclick.html',
                                 'label'       => 'edit',
                                 'js_action'   => qq{
                                   '${p}edit/bulk-part_pkg.html?' + \$('input[name=pkgpart]').serialize()
                                 },
                                 'actionlabel' => 'Bulk edit packages',
                                 'width'       => 960,
                                 'height'      => 420,
                               )
                   },
                   { label  => 'change customers packages',
                     onclick=> include('/elements/popup_link_onclick.html',
                                 'label'       => 'change',
                                 'js_action'   => qq{
                                   '${p}edit/bulk-cust_pkg.html?' + \$('input[name=pkgpart]').serialize()
                                 },
                                 'actionlabel' => 'Change customer packages',
                                 'width'       => 960,
                                 'height'      => 420,
                               )
                   },
                 ],
               ).
               '</FORM>';
}

my @menubar;
# show this if there are any voip_cdr packages defined
if ( FS::part_pkg->count("plan = 'voip_cdr'") ) {
  push @menubar, 'Per-package usage minutes' => $p.'browse/part_pkg_usage.html';
}
</%init>
