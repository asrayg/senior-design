/*
 * File: MultiRateComponent.h
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

#ifndef MultiRateComponent_h_
#define MultiRateComponent_h_
#ifndef MultiRateComponent_COMMON_INCLUDES_
#define MultiRateComponent_COMMON_INCLUDES_
#include "rtwtypes.h"
#endif                                 /* MultiRateComponent_COMMON_INCLUDES_ */

#include "MultiRateComponent_types.h"
#include "services.h"

/* Block signals and states (default storage) for system '<Root>' */
typedef struct {
  real_T F1State;                      /* '<S1>/Unit Delay' */
  real_T F2State;                      /* '<S2>/Unit Delay' */
} D_Work;

/* Block signals and states (default storage) */
extern D_Work rtDWork;

/* Model entry point functions */
extern void MultiRateComponent_initialize(void);
extern void MultiRateComponent_terminate(void);

/* Exported entry point function */
extern void MultiRateComponent_Periodic(void);/* Explicit Task: Periodic */

/* Exported entry point function */
extern void MultiRateComponent_Aperiodic(void);

/*-
 * The generated code includes comments that allow you to trace directly
 * back to the appropriate location in the model.  The basic format
 * is <system>/block_name, where system is the system number (uniquely
 * assigned by Simulink) and block_name is the name of the block.
 *
 * Use the MATLAB hilite_system command to trace the generated code back
 * to the model.  For example,
 *
 * hilite_system('<S3>')    - opens system 3
 * hilite_system('<S3>/Kp') - opens and selects block Kp which resides in S3
 *
 * Here is the system hierarchy for this model
 *
 * '<Root>' : 'MultiRateComponent'
 * '<S1>'   : 'MultiRateComponent/F1'
 * '<S2>'   : 'MultiRateComponent/F2'
 * '<S3>'   : 'MultiRateComponent/Init'
 * '<S4>'   : 'MultiRateComponent/Term'
 */

/*-
 * Requirements for '<Root>': MultiRateComponent


 */
#endif                                 /* MultiRateComponent_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
