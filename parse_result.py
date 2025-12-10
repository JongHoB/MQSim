#!/usr/bin/env python3
"""Summarize MQSim XML result files for NVMe SSD architecture project.

This script parses MQSim XML result files and produces a CSV with:

1. Host-visible I/O metrics
   - Total requests, read/write counts
   - IOPS, throughput (bytes/s and MiB/s)
   - Average device response time and end-to-end request delay
2. Internal controller metrics
   - FTL / CMT statistics (GC executions, mapping/cache hit ratio, etc.)
   - Transaction Scheduling Unit (TSU) statistics for User / GC / Mapping
3. Per-package (flash chip) activity
   - Fractions of time in execution, data transfer, overlapped, idle
4. A simple *relative* energy-per-I/O index using a configurable power model.

Usage
-----
    python parse_mqsim_results.py \
        --input_dir /path/to/xml/results \
        --output_csv mqsim_summary.csv
        
   python3 parse_result.py --input_dir ./results --output_csv mqsim_summary.csv

You can edit the POWER_MODEL dictionary in this file to change the
weights used for the energy index.

The script is intentionally conservative: if some tag/field is missing
in a result file, that column is left empty for that row instead of
crashing.
"""

import argparse
import csv
import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional

# ----------------------------------------------------------------------
# Simple per-state power model (arbitrary units, only for relative comparison)
# ----------------------------------------------------------------------
POWER_MODEL = {
    "exec": 1.0,       # power when a chip is executing flash commands
    "dataxfer": 0.8,   # power during data transfer
    "overlap": 1.1,    # power when data transfer and execution overlap
    "idle": 0.3,       # idle / background power
}


def parse_args():
    p = argparse.ArgumentParser(
        description="Summarize MQSim XML results into a single CSV file."
    )
    p.add_argument(
        "--input_dir",
        required=True,
        help="Directory containing MQSim XML result files (wl_*.xml).",
    )
    p.add_argument(
        "--output_csv",
        required=True,
        help="Path of the output CSV file.",
    )
    return p.parse_args()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def safe_int(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def safe_float(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def get_child_text(parent: ET.Element, tag: str) -> Optional[str]:
    elem = parent.find(tag)
    return elem.text if elem is not None else None


# ----------------------------------------------------------------------
# Experiment name parser (wl_cache…, wl_ch…, wl_ioqd…, wl_tpcc_…)
# ----------------------------------------------------------------------
def parse_experiment_name(filename: str) -> Dict[str, Any]:
    """Parse MQSim result filename into structured fields.

    Examples
    --------
    wl_cache128MB_4kb_randread_scenario_1.xml
    wl_ch4_chip2_4kb_randread_scenario_1.xml
    wl_ioqd32_4kb_randwrite_scenario_1.xml
    wl_tpcc_cache1GB_scenario_1.xml
    wl_tpcc_ch4_chip2_scenario_1.xml
    wl_tpcc_ioqd8_scenario_1.xml
    """
    base = os.path.basename(filename)
    if base.lower().endswith(".xml"):
        base = base[:-4]

    parts = base.split("_")
    info: Dict[str, Any] = {
        "exp_name": base,
        "category": None,
        "cache_size": None,
        "channels": None,
        "chips_per_channel": None,
        "io_queue_depth": None,
        "block_size": None,
        "access_pattern": None,   # randread, randwrite, seqread, seqwrite, mixed, tpcc
        "tpcc_variant": None,     # cache, ch, ioqd
    }

    if len(parts) < 2 or parts[0] != "wl":
        return info

    kind = parts[1]

    # Cache experiments: wl_cache128MB_4kb_randread_scenario_1
    if kind.startswith("cache"):
        info["category"] = "cache"
        info["cache_size"] = kind[len("cache") :]  # e.g., 0MB, 128MB, 256MB, 1GB
        if len(parts) >= 4:
            info["block_size"] = parts[2]          # 4kb, 128kb
            info["access_pattern"] = parts[3]      # randread, randwrite, seqread, seqwrite, mixed

    # Channel/chip scaling: wl_ch4_chip2_4kb_randread_scenario_1
    elif kind.startswith("ch"):
        info["category"] = "ch_chip"
        m = re.match(r"ch(\d+)", kind)
        if m:
            info["channels"] = safe_int(m.group(1))
        if len(parts) >= 3 and parts[2].startswith("chip"):
            m2 = re.match(r"chip(\d+)", parts[2])
            if m2:
                info["chips_per_channel"] = safe_int(m2.group(1))
        if len(parts) >= 5:
            info["block_size"] = parts[3]
            info["access_pattern"] = parts[4]

    # IO queue depth scaling: wl_ioqd32_4kb_randwrite_scenario_1
    elif kind.startswith("ioqd"):
        info["category"] = "ioqd"
        m = re.match(r"ioqd(\d+)", kind)
        if m:
            info["io_queue_depth"] = safe_int(m.group(1))
        if len(parts) >= 4:
            info["block_size"] = parts[2]
            info["access_pattern"] = parts[3]

    # TPCC-based experiments: wl_tpcc_cache1GB_scenario_1, wl_tpcc_ch4_chip2_scenario_1, wl_tpcc_ioqd8_scenario_1
    elif kind == "tpcc":
        info["category"] = "tpcc"
        info["access_pattern"] = "tpcc"
        if len(parts) >= 3:
            sub = parts[2]
            if sub.startswith("cache"):
                info["tpcc_variant"] = "cache"
                info["cache_size"] = sub[len("cache") :]
            elif sub.startswith("ch"):
                info["tpcc_variant"] = "ch_chip"
                m = re.match(r"ch(\d+)", sub)
                if m:
                    info["channels"] = safe_int(m.group(1))
                if len(parts) >= 4 and parts[3].startswith("chip"):
                    m2 = re.match(r"chip(\d+)", parts[3])
                    if m2:
                        info["chips_per_channel"] = safe_int(m2.group(1))
            elif sub.startswith("ioqd"):
                info["tpcc_variant"] = "ioqd"
                m = re.match(r"ioqd(\d+)", sub)
                if m:
                    info["io_queue_depth"] = safe_int(m.group(1))

    return info


# ----------------------------------------------------------------------
# Parsers for each section of the XML
# ----------------------------------------------------------------------
def parse_host_metrics(root: ET.Element) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    host = root.find("Host/Host.IO_Flow")
    if host is None:
        return out

    # Basic counts and IOPS
    out["host_Request_Count"]        = safe_int(get_child_text(host, "Request_Count"))
    out["host_Read_Request_Count"]   = safe_int(get_child_text(host, "Read_Request_Count"))
    out["host_Write_Request_Count"]  = safe_int(get_child_text(host, "Write_Request_Count"))

    out["host_IOPS"]                 = safe_float(get_child_text(host, "IOPS"))
    out["host_Read_IOPS"]            = safe_float(get_child_text(host, "Read_IOPS"))
    out["host_Write_IOPS"]           = safe_float(get_child_text(host, "Write_IOPS"))

    # Bandwidth is reported by MQSim in bytes/second
    bw_total = safe_float(get_child_text(host, "Bandwidth"))
    bw_read  = safe_float(get_child_text(host, "Read_Bandwidth"))
    bw_write = safe_float(get_child_text(host, "Write_Bandwidth"))

    out["host_BW_Bytes_per_s"]       = bw_total
    out["host_Read_BW_Bytes_per_s"]  = bw_read
    out["host_Write_BW_Bytes_per_s"] = bw_write

    mib = 1024.0 * 1024.0
    if bw_total is not None:
        out["host_BW_MiB_per_s"] = bw_total / mib
    if bw_read is not None:
        out["host_Read_BW_MiB_per_s"] = bw_read / mib
    if bw_write is not None:
        out["host_Write_BW_MiB_per_s"] = bw_write / mib

    # Latency (MQSim units; often nanoseconds or microseconds depending on build)
    dev_resp = safe_float(get_child_text(host, "Device_Response_Time"))
    e2e_delay = safe_float(get_child_text(host, "End_to_End_Request_Delay"))

    out["host_Device_Response_Time"] = dev_resp
    out["host_End_to_End_Request_Delay"] = e2e_delay

    # For convenience we also export a "latency_ms" assuming time unit is microseconds.
    # If your build uses different units, rescale accordingly.
    if e2e_delay is not None:
        out["host_E2E_Latency_ms_assuming_us"] = e2e_delay / 1000.0

    return out


def parse_ftl_metrics(root: ET.Element) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    ftl = root.find("SSDDevice/SSDDevice.FTL")
    if ftl is None:
        return out

    # --- Flash command counts -------------------------------------------------
    total_read = 0
    total_prog = 0
    total_erase = 0
    mapping_read = 0
    mapping_prog = 0
    mapping_erase = 0

    for name, val in ftl.attrib.items():
        cnt = safe_int(val)
        if cnt is None:
            continue
        # "Issued_Flash_Read_CMD", "Issued_Flash_Program_CMD", "Issued_Flash_Erase_CMD", etc.
        if "Read_CMD" in name and "For_Mapping" not in name:
            total_read += cnt
        if "Program_CMD" in name and "For_Mapping" not in name:
            total_prog += cnt
        if "Erase_CMD" in name and "For_Mapping" not in name:
            total_erase += cnt

        if "Read_CMD_For_Mapping" in name:
            mapping_read += cnt
        if "Program_CMD_For_Mapping" in name:
            mapping_prog += cnt
        if "Erase_CMD_For_Mapping" in name:
            mapping_erase += cnt

    out["ftl_Total_Flash_Read_CMD"] = total_read
    out["ftl_Total_Flash_Program_CMD"] = total_prog
    out["ftl_Total_Flash_Erase_CMD"] = total_erase

    out["ftl_Mapping_Read_CMD"] = mapping_read
    out["ftl_Mapping_Program_CMD"] = mapping_prog
    out["ftl_Mapping_Erase_CMD"] = mapping_erase

    # --- CMT / address mapping stats -----------------------------------------
    total_queries = safe_int(ftl.attrib.get("Total_CMT_Queries", None))
    hits = safe_int(ftl.attrib.get("CMT_Hits", None))
    total_read_queries = safe_int(ftl.attrib.get("Total_CMT_Read_Queries", None))
    read_hits = safe_int(ftl.attrib.get("CMT_Read_Hits", None))
    total_write_queries = safe_int(ftl.attrib.get("Total_CMT_Write_Queries", None))
    write_hits = safe_int(ftl.attrib.get("CMT_Write_Hits", None))

    out["ftl_Total_CMT_Queries"] = total_queries
    out["ftl_CMT_Hits"] = hits
    out["ftl_Total_CMT_Read_Queries"] = total_read_queries
    out["ftl_CMT_Read_Hits"] = read_hits
    out["ftl_Total_CMT_Write_Queries"] = total_write_queries
    out["ftl_CMT_Write_Hits"] = write_hits

    def ratio(num: Optional[int], den: Optional[int]) -> Optional[float]:
        if num is None or den is None or den == 0:
            return None
        return float(num) / float(den)

    out["ftl_CMT_Hit_Rate"] = ratio(hits, total_queries)
    out["ftl_CMT_Read_Hit_Rate"] = ratio(read_hits, total_read_queries)
    out["ftl_CMT_Write_Hit_Rate"] = ratio(write_hits, total_write_queries)

    # --- GC stats -------------------------------------------------------------
    out["ftl_Total_GC_Executions"] = safe_int(ftl.attrib.get("Total_GC_Executions", None))
    out["ftl_Average_Page_Movement_For_GC"] = safe_float(
        ftl.attrib.get("Average_Page_Movement_For_GC", None)
    )

    return out


def parse_tsu_metrics(root: ET.Element) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    tsu = root.find("SSDDevice/SSDDevice.TSU")
    if tsu is None:
        return out

    prefixes = ("User", "GC", "Mapping")

    # Accumulate per-prefix stats
    stats: Dict[str, Dict[str, float]] = {}
    for prefix in prefixes:
        stats[prefix] = {
            "enq": 0.0,
            "deq": 0.0,
            "wait_time_sum": 0.0,   # weighted by enqueued transactions
            "queue_len_sum": 0.0,   # simple sum over queues
            "queue_entries": 0.0,
        }

    for q in tsu:
        name = q.attrib.get("Name", "")
        if "_" in name:
            prefix = name.split("_", 1)[0]
        else:
            prefix = name
        if prefix not in prefixes:
            continue

        enq = safe_int(q.attrib.get("No_Of_Transactions_Enqueued", None)) or 0
        deq = safe_int(q.attrib.get("No_Of_Transactions_Dequeued", None)) or 0
        avg_wait = safe_float(q.attrib.get("Avg_Transaction_Waiting_Time", None)) or 0.0
        avg_q_len = safe_float(q.attrib.get("Avg_Queue_Length", None)) or 0.0

        s = stats[prefix]
        s["enq"] += enq
        s["deq"] += deq
        s["wait_time_sum"] += avg_wait * enq
        s["queue_len_sum"] += avg_q_len
        s["queue_entries"] += 1.0

    # Convert to averages
    for prefix in prefixes:
        s = stats[prefix]
        enq = s["enq"] or 0.0
        entries = s["queue_entries"] or 0.0

        out[f"tsu_{prefix}_Transactions_Enqueued"] = s["enq"] if s["enq"] > 0 else None
        out[f"tsu_{prefix}_Transactions_Dequeued"] = s["deq"] if s["deq"] > 0 else None

        if enq > 0:
            out[f"tsu_{prefix}_Avg_Waiting_Time"] = s["wait_time_sum"] / enq
        else:
            out[f"tsu_{prefix}_Avg_Waiting_Time"] = None

        if entries > 0:
            out[f"tsu_{prefix}_Avg_Queue_Length"] = s["queue_len_sum"] / entries
        else:
            out[f"tsu_{prefix}_Avg_Queue_Length"] = None

    return out


def parse_chip_metrics_and_energy(root: ET.Element, host_reqs: Optional[int]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    chips = root.findall("SSDDevice/SSDDevice.FlashChips")
    if not chips:
        return out

    n = float(len(chips))

    # Simple averages across all chips
    sum_exec = sum(
        safe_float(ch.attrib.get("Fraction_of_Time_in_Execution", "0")) or 0.0
        for ch in chips
    )
    sum_data = sum(
        safe_float(ch.attrib.get("Fraction_of_Time_in_DataXfer", "0")) or 0.0
        for ch in chips
    )
    sum_overlap = sum(
        safe_float(ch.attrib.get("Fraction_of_Time_in_DataXfer_and_Execution", "0")) or 0.0
        for ch in chips
    )
    sum_idle = sum(
        safe_float(ch.attrib.get("Fraction_of_Time_Idle", "0")) or 0.0
        for ch in chips
    )

    out["chip_Avg_Fraction_Exec"] = sum_exec / n
    out["chip_Avg_Fraction_DataXfer"] = sum_data / n
    out["chip_Avg_Fraction_Overlap"] = sum_overlap / n
    out["chip_Avg_Fraction_Idle"] = sum_idle / n

    # Energy index: very simple model based on the above fractions
    # NOTE: These fractions in MQSim are not strictly exclusive,
    # so this is only a *relative* heuristic, not an exact energy model.
    total_power_index = 0.0
    for ch in chips:
        f_exec = safe_float(ch.attrib.get("Fraction_of_Time_in_Execution", "0")) or 0.0
        f_data = safe_float(ch.attrib.get("Fraction_of_Time_in_DataXfer", "0")) or 0.0
        f_overlap = safe_float(
            ch.attrib.get("Fraction_of_Time_in_DataXfer_and_Execution", "0")
        ) or 0.0
        f_idle = safe_float(ch.attrib.get("Fraction_of_Time_Idle", "0")) or 0.0

        power_index = (
            f_exec * POWER_MODEL["exec"]
            + f_data * POWER_MODEL["dataxfer"]
            + f_overlap * POWER_MODEL["overlap"]
            + f_idle * POWER_MODEL["idle"]
        )
        total_power_index += power_index

    out["energy_Total_Chip_Power_Index"] = total_power_index

    if host_reqs and host_reqs > 0:
        out["energy_Energy_per_IO_Index"] = total_power_index / float(host_reqs)
    else:
        out["energy_Energy_per_IO_Index"] = None

    return out


# ----------------------------------------------------------------------
# Main aggregation
# ----------------------------------------------------------------------
def summarize_file(path: str) -> Dict[str, Any]:
    row: Dict[str, Any] = {}

    # Experiment meta from filename
    row.update(parse_experiment_name(path))

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        # Record the error but keep going
        row["parse_error"] = str(e)
        return row

    # Host metrics
    host = parse_host_metrics(root)
    row.update(host)

    host_req_cnt = host.get("host_Request_Count", None)

    # FTL metrics
    row.update(parse_ftl_metrics(root))

    # TSU (user / mapping / GC transaction stats)
    row.update(parse_tsu_metrics(root))

    # Chip-level activity and simple energy index
    row.update(parse_chip_metrics_and_energy(root, host_req_cnt))

    return row


def main():
    args = parse_args()
    input_dir = args.input_dir
    output_csv = args.output_csv

    # Collect all XML files in the directory
    xml_files = [
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.lower().endswith(".xml") and f.startswith("wl_")
    ]
    xml_files.sort()

    if not xml_files:
        raise SystemExit(f"No wl_*.xml files found in {input_dir!r}")

    rows = [summarize_file(p) for p in xml_files]

    # Determine CSV header as the union of all keys (sorted for stability)
    all_keys = set()
    for r in rows:
        all_keys.update(r.keys())
    header = sorted(all_keys)

    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Wrote summary for {len(rows)} MQSim result files to {output_csv}")


if __name__ == "__main__":
    main()

