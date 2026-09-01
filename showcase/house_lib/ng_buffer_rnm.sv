`timescale 1ns/1ps
// Northgate unity-gain analog buffer, hand-written RNM.
// House style: analog ports are ng_anet, package imported by name.
module ng_buffer_rnm import ng_ams_pkg::*; (
  input  ng_anet ain,
  output ng_anet aout
);
  real out_r;
  assign aout = out_r;
  always @(ain) out_r = (ain < 0.0)          ? 0.0
                      : (ain > NG_VDD_NOM)   ? NG_VDD_NOM
                                             : ain;
endmodule
