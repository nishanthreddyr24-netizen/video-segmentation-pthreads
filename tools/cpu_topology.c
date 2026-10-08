/* cpu_topology.c - ask Windows which logical CPU is which (core, efficiency class).
 * EfficiencyClass: higher = faster "performance" core, 0 = efficiency core on hybrid CPUs.
 * build: gcc -O2 -o tools/cpu_topology.exe tools/cpu_topology.c            */
#define _WIN32_WINNT 0x0A00
#include <stdio.h>
#include <stdlib.h>
#include <windows.h>

int main(void) {
    ULONG len = 0;
    GetSystemCpuSetInformation(NULL, 0, &len, GetCurrentProcess(), 0);
    BYTE *buf = malloc(len);
    if (!GetSystemCpuSetInformation((PSYSTEM_CPU_SET_INFORMATION)buf, len, &len,
                                    GetCurrentProcess(), 0)) {
        fprintf(stderr, "GetSystemCpuSetInformation failed (%lu)\n", GetLastError());
        return 1;
    }
    printf("logical,core,efficiency_class,llc_group,numa\n");
    for (BYTE *p = buf; p < buf + len;) {
        PSYSTEM_CPU_SET_INFORMATION s = (PSYSTEM_CPU_SET_INFORMATION)p;
        if (s->Type == CpuSetInformation)
            printf("%d,%d,%d,%d,%d\n", s->CpuSet.LogicalProcessorIndex, s->CpuSet.CoreIndex,
                   s->CpuSet.EfficiencyClass, s->CpuSet.LastLevelCacheIndex,
                   s->CpuSet.NumaNodeIndex);
        p += s->Size;
    }
    return 0;
}
