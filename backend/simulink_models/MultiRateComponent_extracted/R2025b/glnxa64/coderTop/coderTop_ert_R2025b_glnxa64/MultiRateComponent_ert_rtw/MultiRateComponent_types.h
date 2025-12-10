/*
 * File: MultiRateComponent_types.h
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

#ifndef MultiRateComponent_types_h_
#define MultiRateComponent_types_h_
#include "rtwtypes.h"
#ifndef DEFINED_TYPEDEF_FOR_SlSignalStatus_
#define DEFINED_TYPEDEF_FOR_SlSignalStatus_

typedef enum {
  OK = 0,                              /* Default value */
  GENERIC_ERROR,
  TIMEOUT,
  DATA_INVALID,
  NO_DATA,
  SERVICE_NOT_AVAILABLE
} SlSignalStatus;

#endif
#endif                                 /* MultiRateComponent_types_h_ */

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
