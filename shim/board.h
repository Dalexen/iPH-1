#pragma once
/*
 * Essential PH-1 (mata, Qualcomm MSM8998) constants. Values marked
 * "unverified" come from the msm8998 reference device trees, not from a
 * PH-1; tools/mata-hwinfo.py prints the real ones from your boot.img.
 */
#define FB_BASE			0x9d400000UL	/* cont_splash_mem (unverified) */
#define FB_BASE_HI16		0x9d40		/* FB_BASE >> 16, for start.S */
#define FB_W			1312
#define FB_H			2560
#define GICD_ADDR		0x17a00000UL
#define GICR_ADDR		0x17b00000UL
#define UFS_ADDR		0x01da4000UL	/* ufshc@1da4000 */
/* MPIDR: Aff1 = cluster (0 little, 1 big), Aff0 = core */
#define CPU_MPIDR(i)		((((uint64_t)(i) & 4) << 6) | ((uint64_t)(i) & 3))
/*
 * The kernel runs on the first big core: the little cores (Cortex-A53 class)
 * have no 16K translation granule, the big cores (Cortex-A73 class) do.
 */
#define BIG_CORE_MPIDR		0x100UL
