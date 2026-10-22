###################################################################

# Created by write_sdc on Tue Oct 13 00:57:04 2026

###################################################################
set sdc_version 2.1

set_units -time ns -resistance kOhm -capacitance pF -voltage V -current mA
set_operating_conditions tt_typical_max_1p00v_25c -library                     \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c
set_wire_load_mode top
set_wire_load_model -name Small -library                                       \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports load_valid]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports load_bank]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {load_count[4]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {load_count[3]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {load_count[2]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {load_count[1]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {load_count[0]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports word_valid]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[31]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[30]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[29]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[28]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[27]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[26]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[25]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[24]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[23]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[22]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[21]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[20]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[19]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[18]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[17]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[16]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[15]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[14]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[13]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[12]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[11]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[10]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[9]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[8]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[7]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[6]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[5]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[4]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[3]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[2]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[1]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {child_id[0]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[31]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[30]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[29]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[28]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[27]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[26]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[25]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[24]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[23]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[22]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[21]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[20]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[19]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[18]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[17]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[16]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[15]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[14]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[13]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[12]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[11]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{header_word[10]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {header_word[9]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {header_word[8]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {header_word[7]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {header_word[6]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {header_word[5]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {header_word[4]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {header_word[3]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {header_word[2]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {header_word[1]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {header_word[0]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports dispatch_valid]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports dispatch_bank]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[31]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[30]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[29]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[28]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[27]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[26]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[25]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[24]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[23]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[22]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[21]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[20]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[19]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[18]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[17]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[16]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[15]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[14]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[13]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[12]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[11]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[10]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[9]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[8]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[7]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[6]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[5]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[4]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[3]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[2]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[1]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{parent_visits[0]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[63]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[62]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[61]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[60]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[59]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[58]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[57]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[56]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[55]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[54]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[53]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[52]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[51]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[50]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[49]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[48]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[47]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[46]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[45]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[44]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[43]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[42]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[41]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[40]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[39]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[38]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[37]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[36]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[35]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[34]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[33]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[32]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[31]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[30]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[29]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[28]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[27]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[26]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[25]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[24]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[23]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[22]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[21]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[20]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[19]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[18]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[17]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[16]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[15]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[14]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[13]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[12]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[11]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports                   \
{exploration[10]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {exploration[9]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {exploration[8]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {exploration[7]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {exploration[6]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {exploration[5]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {exploration[4]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {exploration[3]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {exploration[2]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {exploration[1]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports {exploration[0]}]
set_driving_cell -lib_cell BUF_X1M_A12TR -library                              \
sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c [get_ports rsp_ready]
set_load -pin_load 0.01 [get_ports load_ready]
set_load -pin_load 0.01 [get_ports word_ready]
set_load -pin_load 0.01 [get_ports load_error]
set_load -pin_load 0.01 [get_ports dispatch_ready]
set_load -pin_load 0.01 [get_ports rsp_valid]
set_load -pin_load 0.01 [get_ports {rsp_child[31]}]
set_load -pin_load 0.01 [get_ports {rsp_child[30]}]
set_load -pin_load 0.01 [get_ports {rsp_child[29]}]
set_load -pin_load 0.01 [get_ports {rsp_child[28]}]
set_load -pin_load 0.01 [get_ports {rsp_child[27]}]
set_load -pin_load 0.01 [get_ports {rsp_child[26]}]
set_load -pin_load 0.01 [get_ports {rsp_child[25]}]
set_load -pin_load 0.01 [get_ports {rsp_child[24]}]
set_load -pin_load 0.01 [get_ports {rsp_child[23]}]
set_load -pin_load 0.01 [get_ports {rsp_child[22]}]
set_load -pin_load 0.01 [get_ports {rsp_child[21]}]
set_load -pin_load 0.01 [get_ports {rsp_child[20]}]
set_load -pin_load 0.01 [get_ports {rsp_child[19]}]
set_load -pin_load 0.01 [get_ports {rsp_child[18]}]
set_load -pin_load 0.01 [get_ports {rsp_child[17]}]
set_load -pin_load 0.01 [get_ports {rsp_child[16]}]
set_load -pin_load 0.01 [get_ports {rsp_child[15]}]
set_load -pin_load 0.01 [get_ports {rsp_child[14]}]
set_load -pin_load 0.01 [get_ports {rsp_child[13]}]
set_load -pin_load 0.01 [get_ports {rsp_child[12]}]
set_load -pin_load 0.01 [get_ports {rsp_child[11]}]
set_load -pin_load 0.01 [get_ports {rsp_child[10]}]
set_load -pin_load 0.01 [get_ports {rsp_child[9]}]
set_load -pin_load 0.01 [get_ports {rsp_child[8]}]
set_load -pin_load 0.01 [get_ports {rsp_child[7]}]
set_load -pin_load 0.01 [get_ports {rsp_child[6]}]
set_load -pin_load 0.01 [get_ports {rsp_child[5]}]
set_load -pin_load 0.01 [get_ports {rsp_child[4]}]
set_load -pin_load 0.01 [get_ports {rsp_child[3]}]
set_load -pin_load 0.01 [get_ports {rsp_child[2]}]
set_load -pin_load 0.01 [get_ports {rsp_child[1]}]
set_load -pin_load 0.01 [get_ports {rsp_child[0]}]
set_load -pin_load 0.01 [get_ports {rsp_score[63]}]
set_load -pin_load 0.01 [get_ports {rsp_score[62]}]
set_load -pin_load 0.01 [get_ports {rsp_score[61]}]
set_load -pin_load 0.01 [get_ports {rsp_score[60]}]
set_load -pin_load 0.01 [get_ports {rsp_score[59]}]
set_load -pin_load 0.01 [get_ports {rsp_score[58]}]
set_load -pin_load 0.01 [get_ports {rsp_score[57]}]
set_load -pin_load 0.01 [get_ports {rsp_score[56]}]
set_load -pin_load 0.01 [get_ports {rsp_score[55]}]
set_load -pin_load 0.01 [get_ports {rsp_score[54]}]
set_load -pin_load 0.01 [get_ports {rsp_score[53]}]
set_load -pin_load 0.01 [get_ports {rsp_score[52]}]
set_load -pin_load 0.01 [get_ports {rsp_score[51]}]
set_load -pin_load 0.01 [get_ports {rsp_score[50]}]
set_load -pin_load 0.01 [get_ports {rsp_score[49]}]
set_load -pin_load 0.01 [get_ports {rsp_score[48]}]
set_load -pin_load 0.01 [get_ports {rsp_score[47]}]
set_load -pin_load 0.01 [get_ports {rsp_score[46]}]
set_load -pin_load 0.01 [get_ports {rsp_score[45]}]
set_load -pin_load 0.01 [get_ports {rsp_score[44]}]
set_load -pin_load 0.01 [get_ports {rsp_score[43]}]
set_load -pin_load 0.01 [get_ports {rsp_score[42]}]
set_load -pin_load 0.01 [get_ports {rsp_score[41]}]
set_load -pin_load 0.01 [get_ports {rsp_score[40]}]
set_load -pin_load 0.01 [get_ports {rsp_score[39]}]
set_load -pin_load 0.01 [get_ports {rsp_score[38]}]
set_load -pin_load 0.01 [get_ports {rsp_score[37]}]
set_load -pin_load 0.01 [get_ports {rsp_score[36]}]
set_load -pin_load 0.01 [get_ports {rsp_score[35]}]
set_load -pin_load 0.01 [get_ports {rsp_score[34]}]
set_load -pin_load 0.01 [get_ports {rsp_score[33]}]
set_load -pin_load 0.01 [get_ports {rsp_score[32]}]
set_load -pin_load 0.01 [get_ports {rsp_score[31]}]
set_load -pin_load 0.01 [get_ports {rsp_score[30]}]
set_load -pin_load 0.01 [get_ports {rsp_score[29]}]
set_load -pin_load 0.01 [get_ports {rsp_score[28]}]
set_load -pin_load 0.01 [get_ports {rsp_score[27]}]
set_load -pin_load 0.01 [get_ports {rsp_score[26]}]
set_load -pin_load 0.01 [get_ports {rsp_score[25]}]
set_load -pin_load 0.01 [get_ports {rsp_score[24]}]
set_load -pin_load 0.01 [get_ports {rsp_score[23]}]
set_load -pin_load 0.01 [get_ports {rsp_score[22]}]
set_load -pin_load 0.01 [get_ports {rsp_score[21]}]
set_load -pin_load 0.01 [get_ports {rsp_score[20]}]
set_load -pin_load 0.01 [get_ports {rsp_score[19]}]
set_load -pin_load 0.01 [get_ports {rsp_score[18]}]
set_load -pin_load 0.01 [get_ports {rsp_score[17]}]
set_load -pin_load 0.01 [get_ports {rsp_score[16]}]
set_load -pin_load 0.01 [get_ports {rsp_score[15]}]
set_load -pin_load 0.01 [get_ports {rsp_score[14]}]
set_load -pin_load 0.01 [get_ports {rsp_score[13]}]
set_load -pin_load 0.01 [get_ports {rsp_score[12]}]
set_load -pin_load 0.01 [get_ports {rsp_score[11]}]
set_load -pin_load 0.01 [get_ports {rsp_score[10]}]
set_load -pin_load 0.01 [get_ports {rsp_score[9]}]
set_load -pin_load 0.01 [get_ports {rsp_score[8]}]
set_load -pin_load 0.01 [get_ports {rsp_score[7]}]
set_load -pin_load 0.01 [get_ports {rsp_score[6]}]
set_load -pin_load 0.01 [get_ports {rsp_score[5]}]
set_load -pin_load 0.01 [get_ports {rsp_score[4]}]
set_load -pin_load 0.01 [get_ports {rsp_score[3]}]
set_load -pin_load 0.01 [get_ports {rsp_score[2]}]
set_load -pin_load 0.01 [get_ports {rsp_score[1]}]
set_load -pin_load 0.01 [get_ports {rsp_score[0]}]
set_load -pin_load 0.01 [get_ports rsp_error]
set_load -pin_load 0.01 [get_ports {occupied[1]}]
set_load -pin_load 0.01 [get_ports {occupied[0]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[15]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[14]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[13]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[12]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[11]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[10]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[9]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[8]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[7]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[6]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[5]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[4]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[3]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[2]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[1]}]
set_load -pin_load 0.01 [get_ports {debug_lane_active[0]}]
create_clock [get_ports clk]  -name core_clk  -period 2  -waveform {0 1}
set_clock_uncertainty 0.05  [get_clocks core_clk]
set_clock_transition -max -rise 0.1 [get_clocks core_clk]
set_clock_transition -max -fall 0.1 [get_clocks core_clk]
set_clock_transition -min -rise 0.1 [get_clocks core_clk]
set_clock_transition -min -fall 0.1 [get_clocks core_clk]
set_false_path   -from [get_ports rst_n]
set_input_delay -clock core_clk  0.2  [get_ports load_valid]
set_input_delay -clock core_clk  0.2  [get_ports load_bank]
set_input_delay -clock core_clk  0.2  [get_ports {load_count[4]}]
set_input_delay -clock core_clk  0.2  [get_ports {load_count[3]}]
set_input_delay -clock core_clk  0.2  [get_ports {load_count[2]}]
set_input_delay -clock core_clk  0.2  [get_ports {load_count[1]}]
set_input_delay -clock core_clk  0.2  [get_ports {load_count[0]}]
set_input_delay -clock core_clk  0.2  [get_ports word_valid]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[31]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[30]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[29]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[28]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[27]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[26]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[25]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[24]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[23]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[22]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[21]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[20]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[19]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[18]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[17]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[16]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[15]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[14]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[13]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[12]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[11]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[10]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[9]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[8]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[7]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[6]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[5]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[4]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[3]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[2]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[1]}]
set_input_delay -clock core_clk  0.2  [get_ports {child_id[0]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[31]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[30]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[29]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[28]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[27]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[26]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[25]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[24]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[23]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[22]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[21]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[20]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[19]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[18]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[17]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[16]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[15]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[14]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[13]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[12]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[11]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[10]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[9]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[8]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[7]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[6]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[5]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[4]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[3]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[2]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[1]}]
set_input_delay -clock core_clk  0.2  [get_ports {header_word[0]}]
set_input_delay -clock core_clk  0.2  [get_ports dispatch_valid]
set_input_delay -clock core_clk  0.2  [get_ports dispatch_bank]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[31]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[30]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[29]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[28]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[27]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[26]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[25]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[24]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[23]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[22]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[21]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[20]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[19]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[18]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[17]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[16]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[15]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[14]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[13]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[12]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[11]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[10]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[9]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[8]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[7]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[6]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[5]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[4]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[3]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[2]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[1]}]
set_input_delay -clock core_clk  0.2  [get_ports {parent_visits[0]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[63]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[62]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[61]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[60]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[59]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[58]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[57]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[56]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[55]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[54]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[53]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[52]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[51]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[50]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[49]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[48]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[47]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[46]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[45]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[44]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[43]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[42]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[41]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[40]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[39]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[38]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[37]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[36]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[35]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[34]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[33]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[32]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[31]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[30]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[29]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[28]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[27]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[26]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[25]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[24]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[23]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[22]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[21]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[20]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[19]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[18]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[17]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[16]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[15]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[14]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[13]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[12]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[11]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[10]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[9]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[8]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[7]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[6]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[5]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[4]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[3]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[2]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[1]}]
set_input_delay -clock core_clk  0.2  [get_ports {exploration[0]}]
set_input_delay -clock core_clk  0.2  [get_ports rsp_ready]
set_output_delay -clock core_clk  0.2  [get_ports load_ready]
set_output_delay -clock core_clk  0.2  [get_ports word_ready]
set_output_delay -clock core_clk  0.2  [get_ports load_error]
set_output_delay -clock core_clk  0.2  [get_ports dispatch_ready]
set_output_delay -clock core_clk  0.2  [get_ports rsp_valid]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[31]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[30]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[29]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[28]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[27]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[26]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[25]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[24]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[23]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[22]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[21]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[20]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[19]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[18]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[17]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[16]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[15]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[14]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[13]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[12]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[11]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[10]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[9]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[8]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[7]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[6]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[5]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[4]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[3]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[2]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_child[0]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[63]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[62]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[61]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[60]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[59]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[58]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[57]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[56]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[55]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[54]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[53]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[52]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[51]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[50]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[49]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[48]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[47]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[46]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[45]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[44]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[43]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[42]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[41]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[40]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[39]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[38]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[37]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[36]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[35]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[34]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[33]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[32]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[31]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[30]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[29]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[28]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[27]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[26]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[25]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[24]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[23]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[22]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[21]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[20]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[19]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[18]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[17]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[16]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[15]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[14]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[13]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[12]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[11]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[10]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[9]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[8]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[7]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[6]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[5]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[4]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[3]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[2]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {rsp_score[0]}]
set_output_delay -clock core_clk  0.2  [get_ports rsp_error]
set_output_delay -clock core_clk  0.2  [get_ports {occupied[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {occupied[0]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[15]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[14]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[13]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[12]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[11]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[10]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[9]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[8]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[7]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[6]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[5]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[4]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[3]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[2]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[1]}]
set_output_delay -clock core_clk  0.2  [get_ports {debug_lane_active[0]}]
