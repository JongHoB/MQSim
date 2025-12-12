#!/usr/bin/env python3
import os
import re
import math

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SUMMARY_CSV = "mqsim_summary.csv"
OUTPUT_ROOT = "plots_v2"


def build_dataframe(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # workload 이름 통합 (synthetic + tpcc)
    def workload_label(row):
        if row["access_pattern"] == "tpcc":
            return "tpcc"
        else:
            return f"{row['access_pattern']}_{row['block_size']}"

    df["workload"] = df.apply(workload_label, axis=1)
    return df


def plot_metric_vs_param(df: pd.DataFrame,
                         param_col: str,
                         metric_col: str,
                         outdir: str,
                         title_suffix: str,
                         xlabel: str):
    use = df.dropna(subset=[param_col, metric_col, "workload"]).copy()
    if use.empty:
        print(f"[skip] {metric_col} ({title_suffix}) 데이터 없음")
        return

    use["x"] = use[param_col].astype(float)

    labels = {
       "host_BW_MiB_per_s" : "Host Bandwidth (MiB/s)",
        "host_IOPS" : "Host IOPS",
        "host_E2E_Latency_ms_assuming_us" : "Host E2E Latency (ms)",
        "tsu_User_Transactions_Enqueued" : "TSU User Transactions Enqueued",
        "ftl_Total_Flash_Read_CMD" : "FTL Total Flash Read CMD",
        "ftl_Total_Flash_Program_CMD" : "FTL Total Flash Program CMD",
        "ftl_Total_Flash_Erase_CMD" : "FTL Total Flash Erase CMD",
        "ftl_CMT_Hit_Rate" : "FTL CMT Hit Rate",
        "ftl_Total_GC_Executions" : "FTL Total GC Executions",
        "chip_Avg_Fraction_Idle" : "Chip Avg Fraction Idle",
        "chip_Avg_Fraction_DataXfer" : "Chip Avg Fraction DataXfer",
        "chip_Avg_Fraction_Exec" : "Chip Avg Fraction Exec",
        "energy_Energy_per_IO_Index" : "Power(Energy/IO)", 
    }
    y_label = labels[metric_col] if metric_col in labels else metric_col

    plt.figure()
    for wl, sub in use.groupby("workload"):
        sub = sub.sort_values("x")
        plt.plot(sub["x"], sub[metric_col], marker="o", label=wl)

    plt.xlabel(xlabel)
    plt.ylabel(y_label)
    plt.title(f"{y_label} vs {title_suffix}")
    plt.grid(True)
    plt.legend()

    os.makedirs(outdir, exist_ok=True)
    fname = f"{metric_col.replace('/','_per_')}_vs_{param_col}_{title_suffix.replace(' ','_')}.png"
    plt.tight_layout()
    path = os.path.join(outdir, fname)
    plt.savefig(path)
    plt.close()
    print("[saved] ", path)


def plot_heatmap_channels_ways(df: pd.DataFrame,
                               metric_col: str,
                               outdir: str):
    """
    channels × chips_per_channel 2D heatmap (workload별)
    """
    use = df.dropna(subset=["channels", "chips_per_channel", metric_col, "workload"]).copy()
    if use.empty:
        print(f"[skip] heatmap {metric_col} 데이터 없음")
        return

    os.makedirs(outdir, exist_ok=True)

    for wl, sub in use.groupby("workload"):
        pivot = sub.pivot(index="chips_per_channel", columns="channels", values=metric_col)

        if pivot.shape[0] < 2 or pivot.shape[1] < 2:
            # 격자점이 너무 적으면 의미가 없음
            continue

        plt.figure()
        im = plt.imshow(pivot.values,
                        origin="lower",
                        aspect="auto")

        plt.colorbar(im, label=metric_col)
        plt.xticks(range(len(pivot.columns)), pivot.columns)
        plt.yticks(range(len(pivot.index)), pivot.index)
        plt.xlabel("Number of channels")
        plt.ylabel("Chips per channel (ways)")
        plt.title(f"{wl}: {metric_col} (channels × ways)")

        fname = f"{metric_col.replace('/','_per_')}_heatmap_{wl}.png"
        plt.tight_layout()
        path = os.path.join(outdir, fname)
        plt.savefig(path)
        plt.close()
        print("[saved] ", path)


def main():
    df = build_dataframe(SUMMARY_CSV)

    metrics = [
        "host_BW_MiB_per_s",
        "host_IOPS",
        "host_E2E_Latency_ms_assuming_us",
        "tsu_User_Transactions_Enqueued",
        "ftl_Total_Flash_Read_CMD",
        "ftl_Total_Flash_Program_CMD",
        "ftl_Total_Flash_Erase_CMD",
        "ftl_CMT_Hit_Rate",
        "ftl_Total_GC_Executions",
        "chip_Avg_Fraction_Idle",
        "chip_Avg_Fraction_DataXfer",
        "chip_Avg_Fraction_Exec",
        "energy_Energy_per_IO_Index",
    ]

    # -------------------------------
    # 1) Flash channels axis
    #    예: chips_per_channel == 4 로 고정 (baseline ways)
    # -------------------------------
    df_ch_axis = df[(df["channels"].notna()) & (df["chips_per_channel"] == 4)].copy()
    ch_dir = os.path.join(OUTPUT_ROOT, "flash_channels_axis_ways4")

    for m in metrics:
        plot_metric_vs_param(df_ch_axis,
                             param_col="channels",
                             metric_col=m,
                             outdir=ch_dir,
                             title_suffix="Flash channels (ways=4)",
                             xlabel="Number of channels")

    # -------------------------------
    # 2) Flash ways axis
    #    예: channels == 8 로 고정 (baseline channels)
    # -------------------------------
    df_ways_axis = df[(df["chips_per_channel"].notna()) & (df["channels"] == 8)].copy()
    ways_dir = os.path.join(OUTPUT_ROOT, "flash_ways_axis_ch8")

    for m in metrics:
        plot_metric_vs_param(df_ways_axis,
                             param_col="chips_per_channel",
                             metric_col=m,
                             outdir=ways_dir,
                             title_suffix="Flash ways (channels=8)",
                             xlabel="Chips per channel (ways)")

    # -------------------------------
    # 3) 전체 2D 효과 보기 (channels × ways heatmap)
    # -------------------------------
    heatmap_dir = os.path.join(OUTPUT_ROOT, "flash_channels_ways_heatmap")
    for m in metrics:
        plot_heatmap_channels_ways(df, m, heatmap_dir)


if __name__ == "__main__":
    main()

