#pragma once
/*
 * Per-board constants. Default is "sweet" (Redmi Note 10 Pro, SM7150);
 * build with -DBOARD_MATA (shim/build.sh BOARD=mata) for the Essential PH-1
 * (MSM8998). Values marked "unverified" come from the msm8998 reference
 * device trees and have not been checked on a real PH-1.
 */
#ifdef BOARD_MATA
#define FB_BASE			0x9d400000UL	/* cont_splash_mem (unverified; see README) */
#define FB_W			1312
#define FB_H			2560
#define GICD_ADDR		0x17a00000UL
#define GICR_ADDR		0x17b00000UL
#define UFS_ADDR		0x01da4000UL	/* ufshc@1da4000 */
#define IMEM_RESTART_REASON_ADDR 0x146bf65cUL	/* qcom,msm-imem @146bf000 + 0x65c (unverified) */
#define PSHOLD_ADDR		0x010ac000UL	/* unverified */
/* MPIDR: Aff1 = cluster (0 little, 1 big), Aff0 = core */
#define CPU_MPIDR(i)		((((uint64_t)(i) & 4) << 6) | ((uint64_t)(i) & 3))
#else
#define FB_BASE			0x9c000000UL	/* reserved-memory cont_splash_region */
#define FB_W			1080
#define FB_H			2400
#define GICD_ADDR		0x17a00000UL
#define GICR_ADDR		0x17a60000UL
#define UFS_ADDR		0x01d84000UL
#define IMEM_RESTART_REASON_ADDR 0x146aa65cUL
#define PSHOLD_ADDR		0x0c264000UL
/* MPIDR: Aff1 = core number */
#define CPU_MPIDR(i)		((uint64_t)(i) << 8)
#endif
