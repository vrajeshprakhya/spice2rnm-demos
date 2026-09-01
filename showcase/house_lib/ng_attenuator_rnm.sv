`timescale 1ns/1ps
// Northgate 2:1 resistive attenuator, hand-written RNM.
module ng_attenuator_rnm import ng_ams_pkg::*; (
  input  ng_anet ain,
  output ng_anet aout
);
  real out_r;
  assign aout = out_r;
  always @(ain) out_r = 0.5 * ain;
endmodule
