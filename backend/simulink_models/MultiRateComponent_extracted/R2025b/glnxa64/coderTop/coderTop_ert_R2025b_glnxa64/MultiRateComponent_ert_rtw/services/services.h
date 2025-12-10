#ifndef services_h
#define services_h
#include "rtwtypes.h"

/* data transfer service interfaces */
extern real_T get_MultiRateComponent_Aperiodic_DataTransferAtF1Outport1(void);
extern void set_MultiRateComponent_Periodic_DataTransferAtF1Outport1(real_T aVal);

/* receiver service interfaces */
extern real_T get_MultiRateComponent_initialize_InNVM(void);
extern real_T get_MultiRateComponent_Periodic_In(void);

/* sender service interfaces */
extern void set_MultiRateComponent_terminate_OutNVM(real_T rtu_OutNVM_value);
extern void set_MultiRateComponent_Aperiodic_Out(real_T rtu_Out_value);

#endif                                 /* services_h */
