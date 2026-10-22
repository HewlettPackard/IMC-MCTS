###################################################################

# Created by write_sdc on Tue Oct 13 00:58:44 2026

###################################################################
set sdc_version 2.1

set_units -time ns -resistance kOhm -capacitance pF -voltage V -current mA
set_operating_conditions tt_typical_max_1p00v_25c -library                     \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c
set_wire_load_mode top
set_wire_load_model -name Small -library                                       \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports clear]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports advance]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports capture_valid]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports capture_bank]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_count[5]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_count[4]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_count[3]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_count[2]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_count[1]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_count[0]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[511]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[510]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[509]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[508]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[507]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[506]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[505]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[504]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[503]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[502]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[501]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[500]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[499]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[498]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[497]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[496]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[495]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[494]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[493]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[492]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[491]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[490]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[489]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[488]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[487]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[486]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[485]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[484]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[483]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[482]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[481]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[480]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[479]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[478]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[477]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[476]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[475]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[474]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[473]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[472]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[471]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[470]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[469]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[468]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[467]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[466]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[465]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[464]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[463]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[462]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[461]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[460]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[459]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[458]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[457]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[456]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[455]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[454]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[453]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[452]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[451]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[450]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[449]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[448]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[447]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[446]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[445]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[444]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[443]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[442]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[441]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[440]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[439]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[438]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[437]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[436]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[435]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[434]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[433]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[432]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[431]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[430]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[429]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[428]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[427]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[426]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[425]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[424]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[423]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[422]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[421]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[420]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[419]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[418]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[417]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[416]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[415]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[414]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[413]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[412]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[411]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[410]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[409]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[408]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[407]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[406]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[405]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[404]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[403]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[402]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[401]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[400]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[399]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[398]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[397]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[396]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[395]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[394]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[393]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[392]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[391]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[390]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[389]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[388]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[387]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[386]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[385]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[384]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[383]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[382]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[381]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[380]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[379]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[378]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[377]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[376]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[375]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[374]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[373]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[372]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[371]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[370]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[369]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[368]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[367]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[366]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[365]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[364]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[363]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[362]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[361]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[360]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[359]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[358]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[357]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[356]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[355]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[354]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[353]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[352]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[351]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[350]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[349]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[348]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[347]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[346]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[345]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[344]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[343]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[342]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[341]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[340]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[339]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[338]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[337]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[336]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[335]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[334]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[333]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[332]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[331]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[330]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[329]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[328]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[327]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[326]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[325]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[324]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[323]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[322]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[321]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[320]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[319]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[318]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[317]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[316]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[315]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[314]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[313]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[312]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[311]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[310]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[309]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[308]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[307]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[306]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[305]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[304]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[303]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[302]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[301]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[300]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[299]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[298]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[297]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[296]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[295]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[294]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[293]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[292]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[291]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[290]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[289]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[288]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[287]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[286]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[285]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[284]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[283]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[282]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[281]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[280]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[279]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[278]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[277]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[276]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[275]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[274]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[273]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[272]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[271]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[270]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[269]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[268]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[267]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[266]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[265]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[264]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[263]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[262]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[261]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[260]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[259]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[258]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[257]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[256]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[255]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[254]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[253]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[252]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[251]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[250]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[249]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[248]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[247]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[246]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[245]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[244]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[243]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[242]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[241]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[240]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[239]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[238]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[237]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[236]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[235]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[234]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[233]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[232]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[231]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[230]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[229]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[228]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[227]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[226]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[225]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[224]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[223]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[222]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[221]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[220]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[219]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[218]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[217]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[216]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[215]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[214]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[213]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[212]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[211]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[210]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[209]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[208]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[207]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[206]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[205]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[204]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[203]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[202]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[201]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[200]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[199]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[198]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[197]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[196]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[195]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[194]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[193]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[192]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[191]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[190]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[189]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[188]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[187]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[186]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[185]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[184]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[183]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[182]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[181]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[180]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[179]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[178]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[177]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[176]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[175]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[174]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[173]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[172]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[171]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[170]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[169]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[168]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[167]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[166]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[165]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[164]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[163]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[162]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[161]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[160]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[159]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[158]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[157]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[156]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[155]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[154]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[153]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[152]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[151]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[150]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[149]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[148]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[147]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[146]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[145]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[144]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[143]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[142]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[141]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[140]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[139]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[138]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[137]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[136]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[135]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[134]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[133]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[132]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[131]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[130]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[129]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[128]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[127]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[126]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[125]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[124]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[123]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[122]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[121]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[120]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[119]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[118]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[117]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[116]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[115]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[114]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[113]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[112]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[111]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[110]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[109]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[108]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[107]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[106]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[105]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[104]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[103]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[102]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[101]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[100]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[99]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[98]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[97]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[96]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[95]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[94]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[93]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[92]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[91]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[90]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[89]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[88]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[87]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[86]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[85]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[84]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[83]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[82]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[81]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[80]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[79]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[78]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[77]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[76]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[75]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[74]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[73]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[72]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[71]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[70]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[69]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[68]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[67]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[66]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[65]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[64]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[63]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[62]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[61]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[60]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[59]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[58]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[57]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[56]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[55]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[54]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[53]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[52]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[51]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[50]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[49]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[48]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[47]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[46]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[45]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[44]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[43]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[42]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[41]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[40]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[39]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[38]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[37]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[36]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[35]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[34]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[33]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[32]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[31]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[30]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[29]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[28]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[27]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[26]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[25]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[24]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[23]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[22]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[21]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[20]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[19]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[18]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[17]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[16]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[15]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[14]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[13]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[12]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[11]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[10]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[9]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[8]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[7]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[6]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[5]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[4]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[3]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[2]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[1]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{capture_data[0]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports group_valid]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports group_bank]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {group_count[5]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {group_count[4]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {group_count[3]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {group_count[2]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {group_count[1]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {group_count[0]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {column_base[6]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {column_base[5]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {column_base[4]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {column_base[3]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {column_base[2]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {column_base[1]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {column_base[0]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {input_shift[3]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {input_shift[2]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {input_shift[1]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {input_shift[0]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports rsp_ready]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[31]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[30]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[29]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[28]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[27]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[26]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[25]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[24]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[23]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[22]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[21]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[20]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[19]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[18]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[17]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[16]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[15]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[14]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[13]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[12]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[11]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[10]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[9]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[8]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[7]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[6]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[5]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[4]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[3]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[2]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[1]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {read_addr[0]}]
set_load -pin_load 0.01 [get_ports capture_ready]
set_load -pin_load 0.01 [get_ports capture_error]
set_load -pin_load 0.01 [get_ports group_ready]
set_load -pin_load 0.01 [get_ports rsp_valid]
set_load -pin_load 0.01 [get_ports rsp_error]
set_load -pin_load 0.01 [get_ports {occupied[1]}]
set_load -pin_load 0.01 [get_ports {occupied[0]}]
set_load -pin_load 0.01 [get_ports {read_data[255]}]
set_load -pin_load 0.01 [get_ports {read_data[254]}]
set_load -pin_load 0.01 [get_ports {read_data[253]}]
set_load -pin_load 0.01 [get_ports {read_data[252]}]
set_load -pin_load 0.01 [get_ports {read_data[251]}]
set_load -pin_load 0.01 [get_ports {read_data[250]}]
set_load -pin_load 0.01 [get_ports {read_data[249]}]
set_load -pin_load 0.01 [get_ports {read_data[248]}]
set_load -pin_load 0.01 [get_ports {read_data[247]}]
set_load -pin_load 0.01 [get_ports {read_data[246]}]
set_load -pin_load 0.01 [get_ports {read_data[245]}]
set_load -pin_load 0.01 [get_ports {read_data[244]}]
set_load -pin_load 0.01 [get_ports {read_data[243]}]
set_load -pin_load 0.01 [get_ports {read_data[242]}]
set_load -pin_load 0.01 [get_ports {read_data[241]}]
set_load -pin_load 0.01 [get_ports {read_data[240]}]
set_load -pin_load 0.01 [get_ports {read_data[239]}]
set_load -pin_load 0.01 [get_ports {read_data[238]}]
set_load -pin_load 0.01 [get_ports {read_data[237]}]
set_load -pin_load 0.01 [get_ports {read_data[236]}]
set_load -pin_load 0.01 [get_ports {read_data[235]}]
set_load -pin_load 0.01 [get_ports {read_data[234]}]
set_load -pin_load 0.01 [get_ports {read_data[233]}]
set_load -pin_load 0.01 [get_ports {read_data[232]}]
set_load -pin_load 0.01 [get_ports {read_data[231]}]
set_load -pin_load 0.01 [get_ports {read_data[230]}]
set_load -pin_load 0.01 [get_ports {read_data[229]}]
set_load -pin_load 0.01 [get_ports {read_data[228]}]
set_load -pin_load 0.01 [get_ports {read_data[227]}]
set_load -pin_load 0.01 [get_ports {read_data[226]}]
set_load -pin_load 0.01 [get_ports {read_data[225]}]
set_load -pin_load 0.01 [get_ports {read_data[224]}]
set_load -pin_load 0.01 [get_ports {read_data[223]}]
set_load -pin_load 0.01 [get_ports {read_data[222]}]
set_load -pin_load 0.01 [get_ports {read_data[221]}]
set_load -pin_load 0.01 [get_ports {read_data[220]}]
set_load -pin_load 0.01 [get_ports {read_data[219]}]
set_load -pin_load 0.01 [get_ports {read_data[218]}]
set_load -pin_load 0.01 [get_ports {read_data[217]}]
set_load -pin_load 0.01 [get_ports {read_data[216]}]
set_load -pin_load 0.01 [get_ports {read_data[215]}]
set_load -pin_load 0.01 [get_ports {read_data[214]}]
set_load -pin_load 0.01 [get_ports {read_data[213]}]
set_load -pin_load 0.01 [get_ports {read_data[212]}]
set_load -pin_load 0.01 [get_ports {read_data[211]}]
set_load -pin_load 0.01 [get_ports {read_data[210]}]
set_load -pin_load 0.01 [get_ports {read_data[209]}]
set_load -pin_load 0.01 [get_ports {read_data[208]}]
set_load -pin_load 0.01 [get_ports {read_data[207]}]
set_load -pin_load 0.01 [get_ports {read_data[206]}]
set_load -pin_load 0.01 [get_ports {read_data[205]}]
set_load -pin_load 0.01 [get_ports {read_data[204]}]
set_load -pin_load 0.01 [get_ports {read_data[203]}]
set_load -pin_load 0.01 [get_ports {read_data[202]}]
set_load -pin_load 0.01 [get_ports {read_data[201]}]
set_load -pin_load 0.01 [get_ports {read_data[200]}]
set_load -pin_load 0.01 [get_ports {read_data[199]}]
set_load -pin_load 0.01 [get_ports {read_data[198]}]
set_load -pin_load 0.01 [get_ports {read_data[197]}]
set_load -pin_load 0.01 [get_ports {read_data[196]}]
set_load -pin_load 0.01 [get_ports {read_data[195]}]
set_load -pin_load 0.01 [get_ports {read_data[194]}]
set_load -pin_load 0.01 [get_ports {read_data[193]}]
set_load -pin_load 0.01 [get_ports {read_data[192]}]
set_load -pin_load 0.01 [get_ports {read_data[191]}]
set_load -pin_load 0.01 [get_ports {read_data[190]}]
set_load -pin_load 0.01 [get_ports {read_data[189]}]
set_load -pin_load 0.01 [get_ports {read_data[188]}]
set_load -pin_load 0.01 [get_ports {read_data[187]}]
set_load -pin_load 0.01 [get_ports {read_data[186]}]
set_load -pin_load 0.01 [get_ports {read_data[185]}]
set_load -pin_load 0.01 [get_ports {read_data[184]}]
set_load -pin_load 0.01 [get_ports {read_data[183]}]
set_load -pin_load 0.01 [get_ports {read_data[182]}]
set_load -pin_load 0.01 [get_ports {read_data[181]}]
set_load -pin_load 0.01 [get_ports {read_data[180]}]
set_load -pin_load 0.01 [get_ports {read_data[179]}]
set_load -pin_load 0.01 [get_ports {read_data[178]}]
set_load -pin_load 0.01 [get_ports {read_data[177]}]
set_load -pin_load 0.01 [get_ports {read_data[176]}]
set_load -pin_load 0.01 [get_ports {read_data[175]}]
set_load -pin_load 0.01 [get_ports {read_data[174]}]
set_load -pin_load 0.01 [get_ports {read_data[173]}]
set_load -pin_load 0.01 [get_ports {read_data[172]}]
set_load -pin_load 0.01 [get_ports {read_data[171]}]
set_load -pin_load 0.01 [get_ports {read_data[170]}]
set_load -pin_load 0.01 [get_ports {read_data[169]}]
set_load -pin_load 0.01 [get_ports {read_data[168]}]
set_load -pin_load 0.01 [get_ports {read_data[167]}]
set_load -pin_load 0.01 [get_ports {read_data[166]}]
set_load -pin_load 0.01 [get_ports {read_data[165]}]
set_load -pin_load 0.01 [get_ports {read_data[164]}]
set_load -pin_load 0.01 [get_ports {read_data[163]}]
set_load -pin_load 0.01 [get_ports {read_data[162]}]
set_load -pin_load 0.01 [get_ports {read_data[161]}]
set_load -pin_load 0.01 [get_ports {read_data[160]}]
set_load -pin_load 0.01 [get_ports {read_data[159]}]
set_load -pin_load 0.01 [get_ports {read_data[158]}]
set_load -pin_load 0.01 [get_ports {read_data[157]}]
set_load -pin_load 0.01 [get_ports {read_data[156]}]
set_load -pin_load 0.01 [get_ports {read_data[155]}]
set_load -pin_load 0.01 [get_ports {read_data[154]}]
set_load -pin_load 0.01 [get_ports {read_data[153]}]
set_load -pin_load 0.01 [get_ports {read_data[152]}]
set_load -pin_load 0.01 [get_ports {read_data[151]}]
set_load -pin_load 0.01 [get_ports {read_data[150]}]
set_load -pin_load 0.01 [get_ports {read_data[149]}]
set_load -pin_load 0.01 [get_ports {read_data[148]}]
set_load -pin_load 0.01 [get_ports {read_data[147]}]
set_load -pin_load 0.01 [get_ports {read_data[146]}]
set_load -pin_load 0.01 [get_ports {read_data[145]}]
set_load -pin_load 0.01 [get_ports {read_data[144]}]
set_load -pin_load 0.01 [get_ports {read_data[143]}]
set_load -pin_load 0.01 [get_ports {read_data[142]}]
set_load -pin_load 0.01 [get_ports {read_data[141]}]
set_load -pin_load 0.01 [get_ports {read_data[140]}]
set_load -pin_load 0.01 [get_ports {read_data[139]}]
set_load -pin_load 0.01 [get_ports {read_data[138]}]
set_load -pin_load 0.01 [get_ports {read_data[137]}]
set_load -pin_load 0.01 [get_ports {read_data[136]}]
set_load -pin_load 0.01 [get_ports {read_data[135]}]
set_load -pin_load 0.01 [get_ports {read_data[134]}]
set_load -pin_load 0.01 [get_ports {read_data[133]}]
set_load -pin_load 0.01 [get_ports {read_data[132]}]
set_load -pin_load 0.01 [get_ports {read_data[131]}]
set_load -pin_load 0.01 [get_ports {read_data[130]}]
set_load -pin_load 0.01 [get_ports {read_data[129]}]
set_load -pin_load 0.01 [get_ports {read_data[128]}]
set_load -pin_load 0.01 [get_ports {read_data[127]}]
set_load -pin_load 0.01 [get_ports {read_data[126]}]
set_load -pin_load 0.01 [get_ports {read_data[125]}]
set_load -pin_load 0.01 [get_ports {read_data[124]}]
set_load -pin_load 0.01 [get_ports {read_data[123]}]
set_load -pin_load 0.01 [get_ports {read_data[122]}]
set_load -pin_load 0.01 [get_ports {read_data[121]}]
set_load -pin_load 0.01 [get_ports {read_data[120]}]
set_load -pin_load 0.01 [get_ports {read_data[119]}]
set_load -pin_load 0.01 [get_ports {read_data[118]}]
set_load -pin_load 0.01 [get_ports {read_data[117]}]
set_load -pin_load 0.01 [get_ports {read_data[116]}]
set_load -pin_load 0.01 [get_ports {read_data[115]}]
set_load -pin_load 0.01 [get_ports {read_data[114]}]
set_load -pin_load 0.01 [get_ports {read_data[113]}]
set_load -pin_load 0.01 [get_ports {read_data[112]}]
set_load -pin_load 0.01 [get_ports {read_data[111]}]
set_load -pin_load 0.01 [get_ports {read_data[110]}]
set_load -pin_load 0.01 [get_ports {read_data[109]}]
set_load -pin_load 0.01 [get_ports {read_data[108]}]
set_load -pin_load 0.01 [get_ports {read_data[107]}]
set_load -pin_load 0.01 [get_ports {read_data[106]}]
set_load -pin_load 0.01 [get_ports {read_data[105]}]
set_load -pin_load 0.01 [get_ports {read_data[104]}]
set_load -pin_load 0.01 [get_ports {read_data[103]}]
set_load -pin_load 0.01 [get_ports {read_data[102]}]
set_load -pin_load 0.01 [get_ports {read_data[101]}]
set_load -pin_load 0.01 [get_ports {read_data[100]}]
set_load -pin_load 0.01 [get_ports {read_data[99]}]
set_load -pin_load 0.01 [get_ports {read_data[98]}]
set_load -pin_load 0.01 [get_ports {read_data[97]}]
set_load -pin_load 0.01 [get_ports {read_data[96]}]
set_load -pin_load 0.01 [get_ports {read_data[95]}]
set_load -pin_load 0.01 [get_ports {read_data[94]}]
set_load -pin_load 0.01 [get_ports {read_data[93]}]
set_load -pin_load 0.01 [get_ports {read_data[92]}]
set_load -pin_load 0.01 [get_ports {read_data[91]}]
set_load -pin_load 0.01 [get_ports {read_data[90]}]
set_load -pin_load 0.01 [get_ports {read_data[89]}]
set_load -pin_load 0.01 [get_ports {read_data[88]}]
set_load -pin_load 0.01 [get_ports {read_data[87]}]
set_load -pin_load 0.01 [get_ports {read_data[86]}]
set_load -pin_load 0.01 [get_ports {read_data[85]}]
set_load -pin_load 0.01 [get_ports {read_data[84]}]
set_load -pin_load 0.01 [get_ports {read_data[83]}]
set_load -pin_load 0.01 [get_ports {read_data[82]}]
set_load -pin_load 0.01 [get_ports {read_data[81]}]
set_load -pin_load 0.01 [get_ports {read_data[80]}]
set_load -pin_load 0.01 [get_ports {read_data[79]}]
set_load -pin_load 0.01 [get_ports {read_data[78]}]
set_load -pin_load 0.01 [get_ports {read_data[77]}]
set_load -pin_load 0.01 [get_ports {read_data[76]}]
set_load -pin_load 0.01 [get_ports {read_data[75]}]
set_load -pin_load 0.01 [get_ports {read_data[74]}]
set_load -pin_load 0.01 [get_ports {read_data[73]}]
set_load -pin_load 0.01 [get_ports {read_data[72]}]
set_load -pin_load 0.01 [get_ports {read_data[71]}]
set_load -pin_load 0.01 [get_ports {read_data[70]}]
set_load -pin_load 0.01 [get_ports {read_data[69]}]
set_load -pin_load 0.01 [get_ports {read_data[68]}]
set_load -pin_load 0.01 [get_ports {read_data[67]}]
set_load -pin_load 0.01 [get_ports {read_data[66]}]
set_load -pin_load 0.01 [get_ports {read_data[65]}]
set_load -pin_load 0.01 [get_ports {read_data[64]}]
set_load -pin_load 0.01 [get_ports {read_data[63]}]
set_load -pin_load 0.01 [get_ports {read_data[62]}]
set_load -pin_load 0.01 [get_ports {read_data[61]}]
set_load -pin_load 0.01 [get_ports {read_data[60]}]
set_load -pin_load 0.01 [get_ports {read_data[59]}]
set_load -pin_load 0.01 [get_ports {read_data[58]}]
set_load -pin_load 0.01 [get_ports {read_data[57]}]
set_load -pin_load 0.01 [get_ports {read_data[56]}]
set_load -pin_load 0.01 [get_ports {read_data[55]}]
set_load -pin_load 0.01 [get_ports {read_data[54]}]
set_load -pin_load 0.01 [get_ports {read_data[53]}]
set_load -pin_load 0.01 [get_ports {read_data[52]}]
set_load -pin_load 0.01 [get_ports {read_data[51]}]
set_load -pin_load 0.01 [get_ports {read_data[50]}]
set_load -pin_load 0.01 [get_ports {read_data[49]}]
set_load -pin_load 0.01 [get_ports {read_data[48]}]
set_load -pin_load 0.01 [get_ports {read_data[47]}]
set_load -pin_load 0.01 [get_ports {read_data[46]}]
set_load -pin_load 0.01 [get_ports {read_data[45]}]
set_load -pin_load 0.01 [get_ports {read_data[44]}]
set_load -pin_load 0.01 [get_ports {read_data[43]}]
set_load -pin_load 0.01 [get_ports {read_data[42]}]
set_load -pin_load 0.01 [get_ports {read_data[41]}]
set_load -pin_load 0.01 [get_ports {read_data[40]}]
set_load -pin_load 0.01 [get_ports {read_data[39]}]
set_load -pin_load 0.01 [get_ports {read_data[38]}]
set_load -pin_load 0.01 [get_ports {read_data[37]}]
set_load -pin_load 0.01 [get_ports {read_data[36]}]
set_load -pin_load 0.01 [get_ports {read_data[35]}]
set_load -pin_load 0.01 [get_ports {read_data[34]}]
set_load -pin_load 0.01 [get_ports {read_data[33]}]
set_load -pin_load 0.01 [get_ports {read_data[32]}]
set_load -pin_load 0.01 [get_ports {read_data[31]}]
set_load -pin_load 0.01 [get_ports {read_data[30]}]
set_load -pin_load 0.01 [get_ports {read_data[29]}]
set_load -pin_load 0.01 [get_ports {read_data[28]}]
set_load -pin_load 0.01 [get_ports {read_data[27]}]
set_load -pin_load 0.01 [get_ports {read_data[26]}]
set_load -pin_load 0.01 [get_ports {read_data[25]}]
set_load -pin_load 0.01 [get_ports {read_data[24]}]
set_load -pin_load 0.01 [get_ports {read_data[23]}]
set_load -pin_load 0.01 [get_ports {read_data[22]}]
set_load -pin_load 0.01 [get_ports {read_data[21]}]
set_load -pin_load 0.01 [get_ports {read_data[20]}]
set_load -pin_load 0.01 [get_ports {read_data[19]}]
set_load -pin_load 0.01 [get_ports {read_data[18]}]
set_load -pin_load 0.01 [get_ports {read_data[17]}]
set_load -pin_load 0.01 [get_ports {read_data[16]}]
set_load -pin_load 0.01 [get_ports {read_data[15]}]
set_load -pin_load 0.01 [get_ports {read_data[14]}]
set_load -pin_load 0.01 [get_ports {read_data[13]}]
set_load -pin_load 0.01 [get_ports {read_data[12]}]
set_load -pin_load 0.01 [get_ports {read_data[11]}]
set_load -pin_load 0.01 [get_ports {read_data[10]}]
set_load -pin_load 0.01 [get_ports {read_data[9]}]
set_load -pin_load 0.01 [get_ports {read_data[8]}]
set_load -pin_load 0.01 [get_ports {read_data[7]}]
set_load -pin_load 0.01 [get_ports {read_data[6]}]
set_load -pin_load 0.01 [get_ports {read_data[5]}]
set_load -pin_load 0.01 [get_ports {read_data[4]}]
set_load -pin_load 0.01 [get_ports {read_data[3]}]
set_load -pin_load 0.01 [get_ports {read_data[2]}]
set_load -pin_load 0.01 [get_ports {read_data[1]}]
set_load -pin_load 0.01 [get_ports {read_data[0]}]
set_load -pin_load 0.01 [get_ports debug_bus_valid]
set_load -pin_load 0.01 [get_ports {debug_bus_index[1]}]
set_load -pin_load 0.01 [get_ports {debug_bus_index[0]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[127]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[126]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[125]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[124]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[123]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[122]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[121]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[120]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[119]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[118]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[117]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[116]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[115]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[114]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[113]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[112]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[111]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[110]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[109]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[108]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[107]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[106]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[105]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[104]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[103]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[102]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[101]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[100]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[99]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[98]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[97]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[96]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[95]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[94]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[93]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[92]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[91]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[90]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[89]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[88]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[87]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[86]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[85]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[84]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[83]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[82]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[81]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[80]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[79]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[78]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[77]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[76]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[75]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[74]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[73]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[72]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[71]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[70]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[69]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[68]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[67]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[66]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[65]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[64]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[63]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[62]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[61]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[60]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[59]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[58]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[57]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[56]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[55]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[54]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[53]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[52]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[51]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[50]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[49]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[48]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[47]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[46]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[45]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[44]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[43]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[42]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[41]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[40]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[39]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[38]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[37]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[36]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[35]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[34]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[33]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[32]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[31]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[30]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[29]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[28]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[27]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[26]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[25]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[24]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[23]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[22]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[21]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[20]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[19]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[18]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[17]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[16]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[15]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[14]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[13]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[12]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[11]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[10]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[9]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[8]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[7]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[6]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[5]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[4]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[3]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[2]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[1]}]
set_load -pin_load 0.01 [get_ports {debug_bus_data[0]}]
set_load -pin_load 0.01 [get_ports {debug_bus_mask[7]}]
set_load -pin_load 0.01 [get_ports {debug_bus_mask[6]}]
set_load -pin_load 0.01 [get_ports {debug_bus_mask[5]}]
set_load -pin_load 0.01 [get_ports {debug_bus_mask[4]}]
set_load -pin_load 0.01 [get_ports {debug_bus_mask[3]}]
set_load -pin_load 0.01 [get_ports {debug_bus_mask[2]}]
set_load -pin_load 0.01 [get_ports {debug_bus_mask[1]}]
set_load -pin_load 0.01 [get_ports {debug_bus_mask[0]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_valid[7]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_valid[6]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_valid[5]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_valid[4]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_valid[3]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_valid[2]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_valid[1]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_valid[0]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[31]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[30]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[29]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[28]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[27]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[26]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[25]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[24]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[23]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[22]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[21]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[20]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[19]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[18]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[17]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[16]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[15]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[14]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[13]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[12]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[11]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[10]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[9]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[8]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[7]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[6]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[5]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[4]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[3]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[2]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[1]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_addr[0]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[95]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[94]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[93]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[92]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[91]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[90]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[89]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[88]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[87]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[86]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[85]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[84]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[83]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[82]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[81]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[80]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[79]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[78]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[77]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[76]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[75]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[74]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[73]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[72]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[71]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[70]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[69]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[68]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[67]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[66]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[65]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[64]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[63]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[62]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[61]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[60]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[59]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[58]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[57]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[56]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[55]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[54]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[53]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[52]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[51]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[50]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[49]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[48]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[47]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[46]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[45]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[44]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[43]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[42]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[41]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[40]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[39]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[38]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[37]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[36]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[35]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[34]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[33]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[32]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[31]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[30]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[29]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[28]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[27]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[26]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[25]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[24]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[23]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[22]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[21]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[20]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[19]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[18]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[17]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[16]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[15]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[14]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[13]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[12]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[11]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[10]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[9]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[8]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[7]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[6]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[5]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[4]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[3]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[2]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[1]}]
set_load -pin_load 0.01 [get_ports {debug_adc_code[0]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_done[7]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_done[6]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_done[5]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_done[4]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_done[3]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_done[2]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_done[1]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_done[0]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_error[7]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_error[6]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_error[5]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_error[4]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_error[3]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_error[2]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_error[1]}]
set_load -pin_load 0.01 [get_ports {debug_cmd_error[0]}]
set_load -pin_load 0.01 [get_ports debug_release]
create_clock [get_ports clk]  -name core_clk  -period 2  -waveform {0 1}
set_clock_uncertainty 0.05  [get_clocks core_clk]
set_clock_transition -min -fall 0.1 [get_clocks core_clk]
set_clock_transition -min -rise 0.1 [get_clocks core_clk]
set_clock_transition -max -fall 0.1 [get_clocks core_clk]
set_clock_transition -max -rise 0.1 [get_clocks core_clk]
set_false_path   -from [get_ports rst_n]
set_input_delay -clock core_clk  0.2  [get_ports clear]
set_input_delay -clock core_clk  0.2  [get_ports advance]
set_input_delay -clock core_clk  0.2  [get_ports capture_valid]
set_input_delay -clock core_clk  0.2  [get_ports capture_bank]
set_input_delay -clock core_clk  0.2  [get_ports {capture_count[5]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_count[4]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_count[3]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_count[2]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_count[1]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_count[0]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[511]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[510]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[509]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[508]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[507]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[506]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[505]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[504]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[503]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[502]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[501]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[500]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[499]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[498]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[497]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[496]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[495]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[494]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[493]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[492]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[491]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[490]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[489]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[488]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[487]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[486]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[485]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[484]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[483]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[482]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[481]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[480]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[479]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[478]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[477]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[476]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[475]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[474]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[473]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[472]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[471]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[470]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[469]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[468]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[467]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[466]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[465]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[464]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[463]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[462]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[461]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[460]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[459]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[458]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[457]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[456]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[455]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[454]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[453]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[452]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[451]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[450]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[449]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[448]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[447]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[446]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[445]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[444]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[443]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[442]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[441]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[440]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[439]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[438]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[437]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[436]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[435]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[434]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[433]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[432]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[431]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[430]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[429]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[428]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[427]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[426]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[425]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[424]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[423]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[422]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[421]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[420]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[419]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[418]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[417]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[416]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[415]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[414]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[413]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[412]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[411]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[410]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[409]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[408]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[407]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[406]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[405]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[404]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[403]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[402]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[401]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[400]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[399]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[398]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[397]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[396]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[395]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[394]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[393]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[392]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[391]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[390]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[389]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[388]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[387]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[386]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[385]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[384]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[383]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[382]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[381]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[380]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[379]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[378]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[377]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[376]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[375]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[374]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[373]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[372]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[371]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[370]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[369]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[368]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[367]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[366]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[365]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[364]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[363]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[362]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[361]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[360]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[359]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[358]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[357]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[356]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[355]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[354]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[353]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[352]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[351]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[350]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[349]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[348]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[347]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[346]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[345]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[344]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[343]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[342]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[341]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[340]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[339]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[338]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[337]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[336]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[335]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[334]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[333]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[332]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[331]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[330]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[329]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[328]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[327]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[326]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[325]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[324]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[323]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[322]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[321]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[320]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[319]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[318]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[317]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[316]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[315]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[314]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[313]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[312]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[311]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[310]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[309]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[308]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[307]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[306]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[305]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[304]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[303]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[302]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[301]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[300]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[299]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[298]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[297]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[296]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[295]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[294]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[293]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[292]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[291]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[290]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[289]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[288]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[287]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[286]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[285]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[284]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[283]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[282]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[281]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[280]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[279]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[278]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[277]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[276]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[275]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[274]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[273]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[272]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[271]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[270]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[269]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[268]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[267]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[266]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[265]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[264]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[263]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[262]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[261]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[260]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[259]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[258]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[257]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[256]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[255]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[254]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[253]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[252]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[251]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[250]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[249]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[248]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[247]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[246]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[245]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[244]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[243]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[242]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[241]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[240]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[239]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[238]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[237]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[236]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[235]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[234]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[233]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[232]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[231]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[230]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[229]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[228]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[227]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[226]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[225]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[224]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[223]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[222]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[221]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[220]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[219]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[218]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[217]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[216]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[215]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[214]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[213]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[212]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[211]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[210]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[209]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[208]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[207]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[206]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[205]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[204]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[203]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[202]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[201]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[200]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[199]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[198]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[197]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[196]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[195]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[194]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[193]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[192]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[191]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[190]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[189]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[188]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[187]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[186]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[185]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[184]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[183]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[182]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[181]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[180]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[179]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[178]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[177]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[176]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[175]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[174]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[173]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[172]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[171]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[170]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[169]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[168]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[167]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[166]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[165]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[164]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[163]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[162]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[161]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[160]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[159]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[158]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[157]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[156]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[155]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[154]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[153]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[152]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[151]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[150]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[149]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[148]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[147]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[146]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[145]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[144]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[143]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[142]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[141]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[140]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[139]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[138]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[137]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[136]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[135]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[134]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[133]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[132]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[131]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[130]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[129]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[128]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[127]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[126]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[125]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[124]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[123]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[122]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[121]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[120]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[119]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[118]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[117]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[116]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[115]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[114]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[113]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[112]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[111]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[110]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[109]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[108]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[107]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[106]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[105]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[104]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[103]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[102]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[101]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[100]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[99]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[98]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[97]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[96]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[95]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[94]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[93]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[92]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[91]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[90]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[89]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[88]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[87]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[86]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[85]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[84]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[83]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[82]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[81]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[80]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[79]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[78]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[77]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[76]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[75]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[74]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[73]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[72]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[71]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[70]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[69]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[68]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[67]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[66]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[65]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[64]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[63]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[62]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[61]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[60]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[59]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[58]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[57]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[56]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[55]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[54]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[53]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[52]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[51]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[50]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[49]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[48]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[47]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[46]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[45]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[44]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[43]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[42]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[41]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[40]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[39]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[38]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[37]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[36]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[35]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[34]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[33]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[32]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[31]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[30]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[29]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[28]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[27]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[26]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[25]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[24]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[23]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[22]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[21]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[20]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[19]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[18]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[17]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[16]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[15]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[14]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[13]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[12]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[11]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[10]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[9]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[8]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[7]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[6]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[5]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[4]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[3]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[2]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[1]}]
set_input_delay -clock core_clk  0.2  [get_ports {capture_data[0]}]
set_input_delay -clock core_clk  0.2  [get_ports group_valid]
set_input_delay -clock core_clk  0.2  [get_ports group_bank]
set_input_delay -clock core_clk  0.2  [get_ports {group_count[5]}]
set_input_delay -clock core_clk  0.2  [get_ports {group_count[4]}]
set_input_delay -clock core_clk  0.2  [get_ports {group_count[3]}]
set_input_delay -clock core_clk  0.2  [get_ports {group_count[2]}]
set_input_delay -clock core_clk  0.2  [get_ports {group_count[1]}]
set_input_delay -clock core_clk  0.2  [get_ports {group_count[0]}]
set_input_delay -clock core_clk  0.2  [get_ports {column_base[6]}]
set_input_delay -clock core_clk  0.2  [get_ports {column_base[5]}]
set_input_delay -clock core_clk  0.2  [get_ports {column_base[4]}]
set_input_delay -clock core_clk  0.2  [get_ports {column_base[3]}]
set_input_delay -clock core_clk  0.2  [get_ports {column_base[2]}]
set_input_delay -clock core_clk  0.2  [get_ports {column_base[1]}]
set_input_delay -clock core_clk  0.2  [get_ports {column_base[0]}]
set_input_delay -clock core_clk  0.2  [get_ports {input_shift[3]}]
set_input_delay -clock core_clk  0.2  [get_ports {input_shift[2]}]
set_input_delay -clock core_clk  0.2  [get_ports {input_shift[1]}]
set_input_delay -clock core_clk  0.2  [get_ports {input_shift[0]}]
set_input_delay -clock core_clk  0.2  [get_ports rsp_ready]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[31]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[30]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[29]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[28]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[27]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[26]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[25]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[24]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[23]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[22]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[21]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[20]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[19]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[18]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[17]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[16]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[15]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[14]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[13]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[12]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[11]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[10]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[9]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[8]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[7]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[6]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[5]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[4]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[3]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[2]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[1]}]
set_input_delay -clock core_clk  0.2  [get_ports {read_addr[0]}]
set_output_delay -clock core_clk  0.2  [get_ports capture_ready]
set_output_delay -clock core_clk  0.2  [get_ports capture_error]
set_output_delay -clock core_clk  0.2  [get_ports group_ready]
set_output_delay -clock core_clk  0.2  [get_ports rsp_valid]
set_output_delay -clock core_clk  0.2  [get_ports rsp_error]
set_output_delay -clock core_clk  0.2  [get_ports {occupied[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {occupied[0]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[255]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[254]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[253]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[252]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[251]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[250]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[249]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[248]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[247]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[246]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[245]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[244]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[243]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[242]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[241]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[240]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[239]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[238]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[237]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[236]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[235]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[234]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[233]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[232]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[231]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[230]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[229]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[228]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[227]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[226]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[225]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[224]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[223]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[222]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[221]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[220]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[219]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[218]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[217]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[216]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[215]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[214]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[213]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[212]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[211]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[210]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[209]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[208]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[207]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[206]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[205]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[204]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[203]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[202]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[201]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[200]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[199]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[198]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[197]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[196]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[195]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[194]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[193]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[192]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[191]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[190]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[189]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[188]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[187]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[186]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[185]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[184]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[183]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[182]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[181]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[180]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[179]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[178]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[177]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[176]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[175]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[174]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[173]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[172]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[171]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[170]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[169]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[168]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[167]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[166]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[165]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[164]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[163]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[162]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[161]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[160]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[159]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[158]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[157]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[156]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[155]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[154]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[153]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[152]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[151]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[150]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[149]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[148]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[147]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[146]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[145]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[144]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[143]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[142]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[141]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[140]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[139]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[138]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[137]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[136]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[135]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[134]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[133]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[132]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[131]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[130]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[129]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[128]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[127]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[126]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[125]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[124]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[123]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[122]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[121]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[120]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[119]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[118]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[117]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[116]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[115]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[114]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[113]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[112]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[111]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[110]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[109]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[108]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[107]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[106]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[105]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[104]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[103]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[102]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[101]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[100]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[99]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[98]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[97]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[96]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[95]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[94]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[93]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[92]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[91]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[90]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[89]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[88]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[87]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[86]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[85]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[84]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[83]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[82]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[81]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[80]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[79]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[78]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[77]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[76]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[75]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[74]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[73]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[72]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[71]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[70]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[69]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[68]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[67]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[66]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[65]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[64]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[63]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[62]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[61]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[60]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[59]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[58]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[57]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[56]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[55]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[54]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[53]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[52]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[51]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[50]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[49]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[48]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[47]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[46]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[45]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[44]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[43]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[42]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[41]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[40]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[39]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[38]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[37]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[36]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[35]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[34]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[33]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[32]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[31]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[30]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[29]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[28]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[27]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[26]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[25]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[24]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[23]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[22]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[21]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[20]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[19]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[18]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[17]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[16]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[15]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[14]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[13]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[12]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[11]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[10]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[9]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[8]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[7]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[6]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[5]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[4]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[3]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[2]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {read_data[0]}]
set_output_delay -clock core_clk  0.2  [get_ports debug_bus_valid]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_index[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_index[0]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[127]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[126]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[125]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[124]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[123]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[122]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[121]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[120]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[119]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[118]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[117]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[116]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[115]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[114]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[113]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[112]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[111]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[110]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[109]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[108]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[107]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[106]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[105]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[104]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[103]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[102]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[101]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[100]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[99]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[98]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[97]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[96]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[95]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[94]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[93]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[92]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[91]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[90]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[89]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[88]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[87]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[86]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[85]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[84]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[83]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[82]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[81]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[80]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[79]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[78]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[77]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[76]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[75]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[74]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[73]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[72]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[71]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[70]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[69]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[68]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[67]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[66]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[65]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[64]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[63]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[62]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[61]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[60]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[59]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[58]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[57]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[56]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[55]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[54]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[53]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[52]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[51]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[50]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[49]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[48]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[47]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[46]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[45]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[44]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[43]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[42]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[41]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[40]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[39]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[38]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[37]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[36]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[35]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[34]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[33]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[32]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[31]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[30]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[29]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[28]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[27]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[26]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[25]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[24]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[23]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[22]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[21]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[20]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[19]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[18]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[17]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[16]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[15]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[14]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[13]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[12]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[11]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[10]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[9]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[8]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[7]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[6]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[5]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[4]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[3]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[2]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_data[0]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_mask[7]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_mask[6]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_mask[5]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_mask[4]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_mask[3]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_mask[2]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_mask[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_bus_mask[0]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_valid[7]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_valid[6]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_valid[5]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_valid[4]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_valid[3]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_valid[2]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_valid[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_valid[0]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[31]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[30]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[29]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[28]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[27]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[26]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[25]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[24]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[23]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[22]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[21]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[20]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[19]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[18]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[17]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[16]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[15]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[14]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[13]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[12]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[11]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[10]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[9]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[8]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[7]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[6]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[5]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[4]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[3]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[2]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_addr[0]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[95]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[94]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[93]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[92]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[91]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[90]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[89]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[88]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[87]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[86]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[85]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[84]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[83]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[82]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[81]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[80]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[79]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[78]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[77]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[76]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[75]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[74]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[73]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[72]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[71]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[70]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[69]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[68]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[67]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[66]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[65]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[64]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[63]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[62]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[61]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[60]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[59]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[58]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[57]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[56]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[55]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[54]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[53]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[52]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[51]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[50]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[49]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[48]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[47]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[46]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[45]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[44]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[43]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[42]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[41]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[40]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[39]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[38]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[37]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[36]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[35]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[34]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[33]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[32]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[31]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[30]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[29]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[28]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[27]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[26]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[25]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[24]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[23]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[22]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[21]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[20]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[19]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[18]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[17]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[16]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[15]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[14]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[13]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[12]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[11]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[10]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[9]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[8]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[7]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[6]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[5]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[4]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[3]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[2]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_adc_code[0]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_done[7]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_done[6]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_done[5]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_done[4]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_done[3]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_done[2]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_done[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_done[0]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_error[7]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_error[6]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_error[5]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_error[4]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_error[3]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_error[2]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_error[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_cmd_error[0]}]
set_output_delay -clock core_clk  0.2  [get_ports debug_release]
