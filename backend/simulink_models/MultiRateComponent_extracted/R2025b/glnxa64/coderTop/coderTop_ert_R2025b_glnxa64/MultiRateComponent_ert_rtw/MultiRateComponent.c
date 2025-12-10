/*
 * File: MultiRateComponent.c
 *
 * Code generated for Simulink model 'MultiRateComponent'.
 *
 * Model version                  : 11.0
 * Simulink Coder version         : 25.2 (R2025b) 28-Jul-2025
 * C/C++ source code generated on : Thu Dec  4 04:23:54 2025
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: Intel->x86-64 (Windows64)
 * Code generation objectives:
 *    1. Execution efficiency
 *    2. Traceability
 * Validation result: Not run
 */

#include "MultiRateComponent.h"
#include "rtwtypes.h"
#include "services.h"

/* Block signals and states (default storage) */
D_Work rtDWork;

/* Model step function for TID1 */
void MultiRateComponent_Periodic(void) /* Explicit Task: Periodic */
{
  real_T rtb_Sum;

  /* RootInportFunctionCallGenerator generated from: '<Root>/Periodic' incorporates:
   *  SubSystem: '<Root>/F1'
   */
  /* Sum: '<S1>/Sum' incorporates:
   *  Inport: '<Root>/In'
   *  UnitDelay: '<S1>/Unit Delay'
   */
  rtb_Sum = get_MultiRateComponent_Periodic_In() + rtDWork.F1State;

  /* Update for UnitDelay: '<S1>/Unit Delay' */
  rtDWork.F1State = rtb_Sum;

  /* End of Outputs for RootInportFunctionCallGenerator generated from: '<Root>/Periodic' */

  /* DataTransferBlock generated from: '<Root>/F1' */
  set_MultiRateComponent_Periodic_DataTransferAtF1Outport1(rtb_Sum);
}

/* Output function */
void MultiRateComponent_Aperiodic(void)
{
  real_T Out;

  /* RootInportFunctionCallGenerator generated from: '<Root>/Aperiodic' incorporates:
   *  SubSystem: '<Root>/F2'
   */
  /* Outport: '<Root>/Out' incorporates:
   *  DataTransferBlock generated from: '<Root>/F1'
   *  Sum: '<S2>/Sum'
   *  UnitDelay: '<S2>/Unit Delay'
   */
  Out = get_MultiRateComponent_Aperiodic_DataTransferAtF1Outport1() +
    rtDWork.F2State;

  /* Update for UnitDelay: '<S2>/Unit Delay' incorporates:
   *  Outport: '<Root>/Out'
   */
  rtDWork.F2State = Out;

  /* End of Outputs for RootInportFunctionCallGenerator generated from: '<Root>/Aperiodic' */

  /* Outport: '<Root>/Out' */
  set_MultiRateComponent_Aperiodic_Out(Out);
}

/* Model initialize function */
void MultiRateComponent_initialize(void)
{
  /* Outputs for Atomic SubSystem: '<Root>/Init' */
  /* StateWriter: '<S3>/State Writer' incorporates:
   *  Inport: '<Root>/InNVM'
   */
  rtDWork.F1State = get_MultiRateComponent_initialize_InNVM();

  /* End of Outputs for SubSystem: '<Root>/Init' */
}

/* Model terminate function */
void MultiRateComponent_terminate(void)
{
  /* Outputs for Atomic SubSystem: '<Root>/Term' */
  /* Terminate for Outport: '<Root>/OutNVM' incorporates:
   *  StateReader: '<S4>/State Reader'
   */
  set_MultiRateComponent_terminate_OutNVM(rtDWork.F1State);

  /* End of Outputs for SubSystem: '<Root>/Term' */
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
