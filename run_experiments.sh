#!/bin/bash
# ============================================================================
# Storage Architecture Project - SSD Bottleneck Analysis
# Repository: JongHoB/MQSim
# 
# Baseline 설정: JongHoB/MQSim/ssdconfig.xml 기반
# Source: https://github.com/JongHoB/MQSim/blob/master/ssdconfig.xml
# ============================================================================

set -e

# ============================================================================
# 디렉토리 설정
# ============================================================================
MQSIM_DIR="$(pwd)"
RESULTS_DIR="${MQSIM_DIR}/results"
CONFIGS_DIR="${MQSIM_DIR}/configs"
WORKLOADS_DIR="${MQSIM_DIR}/workloads"

mkdir -p "${RESULTS_DIR}"
mkdir -p "${CONFIGS_DIR}"
mkdir -p "${WORKLOADS_DIR}"

# ============================================================================
# Baseline 값 (JongHoB/MQSim/ssdconfig.xml 그대로)
# ============================================================================
BASELINE_IO_QUEUE_DEPTH=256
BASELINE_DATA_CACHE_CAPACITY=268435456    # 256 MB
BASELINE_FLASH_CHANNEL_COUNT=8
BASELINE_CHIP_NO_PER_CHANNEL=4

# ============================================================================
# 실험 파라미터 (Proposal 기반)
# ============================================================================

# 실험 1: NVMe Queueing (Host-side) - IO_Queue_Depth 변화
IO_QUEUE_DEPTHS=(1 8 32 128 256)

# 실험 2: DRAM Buffer - Data_Cache_Capacity 변화
DATA_CACHE_CAPACITIES=(0 134217728 268435456 1073741824)
DATA_CACHE_LABELS=("0MB" "128MB" "256MB" "1GB")

# 실험 3: Flash Parallelism - Channel/Chip 변화
FLASH_CHANNEL_COUNTS=(4 8 16)
CHIP_NO_PER_CHANNELS=(2 4 8)

# Workload 파라미터
# 4KB random: request_size=8 sectors, address=RANDOM_UNIFORM
# 128KB sequential: request_size=256 sectors, address=STREAMING
WORKLOAD_QUEUE_DEPTH=256  # SSD 큐를 포화시키기 위해 높은 값


TRACE_FILE="traces/tpcc-small.trace"

# ============================================================================
# SSD Config 생성 함수
# 모든 값은 JongHoB/MQSim/ssdconfig.xml 원본 그대로 사용
# 변경하는 파라미터만 인자로 받음
# ============================================================================
generate_ssd_config() {
    local output_file=$1
    local io_queue_depth=$2
    local data_cache_capacity=$3
    local flash_channel_count=$4
    local chip_no_per_channel=$5
    
    cat > "${output_file}" << 'XMLEOF'
<?xml version="1.0" encoding="us-ascii"?>
<Execution_Parameter_Set>
	<Host_Parameter_Set>
		<PCIe_Lane_Bandwidth>1.00000</PCIe_Lane_Bandwidth>
		<PCIe_Lane_Count>4</PCIe_Lane_Count>
		<SATA_Processing_Delay>400000</SATA_Processing_Delay>
		<Enable_ResponseTime_Logging>true</Enable_ResponseTime_Logging>
		<ResponseTime_Logging_Period_Length>1000000</ResponseTime_Logging_Period_Length>
	</Host_Parameter_Set>
	<Device_Parameter_Set>
		<Seed>321</Seed>
		<Enabled_Preconditioning>true</Enabled_Preconditioning>
		<Memory_Type>FLASH</Memory_Type>
		<HostInterface_Type>NVME</HostInterface_Type>
XMLEOF

    # 변경되는 파라미터들
    echo "		<IO_Queue_Depth>${io_queue_depth}</IO_Queue_Depth>" >> "${output_file}"
    
    cat >> "${output_file}" << 'XMLEOF'
		<Queue_Fetch_Size>512</Queue_Fetch_Size>
		<Caching_Mechanism>ADVANCED</Caching_Mechanism>
		<Data_Cache_Sharing_Mode>SHARED</Data_Cache_Sharing_Mode>
XMLEOF

    echo "		<Data_Cache_Capacity>${data_cache_capacity}</Data_Cache_Capacity>" >> "${output_file}"

    cat >> "${output_file}" << 'XMLEOF'
		<Data_Cache_DRAM_Row_Size>8192</Data_Cache_DRAM_Row_Size>
		<Data_Cache_DRAM_Data_Rate>400</Data_Cache_DRAM_Data_Rate>
		<Data_Cache_DRAM_Data_Busrt_Size>2</Data_Cache_DRAM_Data_Busrt_Size>
		<Data_Cache_DRAM_tRCD>13</Data_Cache_DRAM_tRCD>
		<Data_Cache_DRAM_tCL>13</Data_Cache_DRAM_tCL>
		<Data_Cache_DRAM_tRP>13</Data_Cache_DRAM_tRP>
		<Address_Mapping>PAGE_LEVEL</Address_Mapping>
		<Ideal_Mapping_Table>true</Ideal_Mapping_Table>
		<CMT_Capacity>2097152</CMT_Capacity>
		<CMT_Sharing_Mode>SHARED</CMT_Sharing_Mode>
		<Plane_Allocation_Scheme>CWDP</Plane_Allocation_Scheme>
		<Transaction_Scheduling_Policy>OUT_OF_ORDER</Transaction_Scheduling_Policy>
		<Overprovisioning_Ratio>0.07</Overprovisioning_Ratio>
		<GC_Exec_Threshold>0.05000</GC_Exec_Threshold>
		<GC_Block_Selection_Policy>RGA</GC_Block_Selection_Policy>
		<Use_Copyback_for_GC>false</Use_Copyback_for_GC>
		<Preemptible_GC_Enabled>false</Preemptible_GC_Enabled>
		<GC_Hard_Threshold>0.005000</GC_Hard_Threshold>
		<Dynamic_Wearleveling_Enabled>true</Dynamic_Wearleveling_Enabled>
		<Static_Wearleveling_Enabled>true</Static_Wearleveling_Enabled>
		<Static_Wearleveling_Threshold>100</Static_Wearleveling_Threshold>
		<Preferred_suspend_erase_time_for_read>700000</Preferred_suspend_erase_time_for_read>
		<Preferred_suspend_erase_time_for_write>700000</Preferred_suspend_erase_time_for_write>
		<Preferred_suspend_write_time_for_read>100000</Preferred_suspend_write_time_for_read>
XMLEOF

    echo "		<Flash_Channel_Count>${flash_channel_count}</Flash_Channel_Count>" >> "${output_file}"

    cat >> "${output_file}" << 'XMLEOF'
		<Flash_Channel_Width>1</Flash_Channel_Width>
		<Channel_Transfer_Rate>333</Channel_Transfer_Rate>
XMLEOF

    echo "		<Chip_No_Per_Channel>${chip_no_per_channel}</Chip_No_Per_Channel>" >> "${output_file}"

    cat >> "${output_file}" << 'XMLEOF'
		<Flash_Comm_Protocol>NVDDR2</Flash_Comm_Protocol>
		<Flash_Parameter_Set>
			<Flash_Technology>MLC</Flash_Technology>
			<CMD_Suspension_Support>ERASE</CMD_Suspension_Support>
			<Page_Read_Latency_LSB>75000</Page_Read_Latency_LSB>
			<Page_Read_Latency_CSB>75000</Page_Read_Latency_CSB>
			<Page_Read_Latency_MSB>75000</Page_Read_Latency_MSB>
			<Page_Program_Latency_LSB>750000</Page_Program_Latency_LSB>
			<Page_Program_Latency_CSB>750000</Page_Program_Latency_CSB>
			<Page_Program_Latency_MSB>750000</Page_Program_Latency_MSB>
			<Block_Erase_Latency>3800000</Block_Erase_Latency>
			<Block_PE_Cycles_Limit>10000</Block_PE_Cycles_Limit>
			<Suspend_Erase_Time>700000</Suspend_Erase_Time>
			<Suspend_Program_Time>100000</Suspend_Program_Time>
			<Die_No_Per_Chip>2</Die_No_Per_Chip>
			<Plane_No_Per_Die>2</Plane_No_Per_Die>
			<Block_No_Per_Plane>2048</Block_No_Per_Plane>
			<Page_No_Per_Block>256</Page_No_Per_Block>
			<Page_Capacity>8192</Page_Capacity>
			<Page_Metadat_Capacity>448</Page_Metadat_Capacity>
		</Flash_Parameter_Set>
	</Device_Parameter_Set>
</Execution_Parameter_Set>
XMLEOF
}

# ============================================================================
# Synthetic Workload 생성 함수
# ============================================================================
generate_synthetic_workload() {
    local output_file=$1
    local read_percentage=$2       # 100=read, 0=write, 70=mixed
    local request_size=$3          # 8=4KB, 256=128KB
    local address_distribution=$4  # RANDOM_UNIFORM or STREAMING
    local queue_depth=$5           # Average_No_of_Reqs_in_Queue
    local channel_count=$6
    local chip_count=$7
    
    # Channel IDs: 0,1,2,... ,channel_count-1
    local channel_ids=""
    for ((i=0; i<channel_count; i++)); do
        [ $i -eq 0 ] && channel_ids="$i" || channel_ids="${channel_ids},$i"
    done
    
    # Chip IDs: 0,1,2,...,chip_count-1
    local chip_ids=""
    for ((i=0; i<chip_count; i++)); do
        [ $i -eq 0 ] && chip_ids="$i" || chip_ids="${chip_ids},$i"
    done
    
    cat > "${output_file}" << EOF
<?xml version="1.0" encoding="us-ascii"?>
<MQSim_IO_Scenarios>
	<IO_Scenario>
		<IO_Flow_Parameter_Set_Synthetic>
			<Priority_Class>HIGH</Priority_Class>
			<Device_Level_Data_Caching_Mode>WRITE_CACHE</Device_Level_Data_Caching_Mode>
			<Channel_IDs>${channel_ids}</Channel_IDs>
			<Chip_IDs>${chip_ids}</Chip_IDs>
			<Die_IDs>0,1</Die_IDs>
			<Plane_IDs>0,1</Plane_IDs>
			<Initial_Occupancy_Percentage>70</Initial_Occupancy_Percentage>
			<Working_Set_Percentage>85</Working_Set_Percentage>
			<Synthetic_Generator_Type>QUEUE_DEPTH</Synthetic_Generator_Type>
			<Read_Percentage>${read_percentage}</Read_Percentage>
			<Address_Distribution>${address_distribution}</Address_Distribution>
			<Percentage_of_Hot_Region>0</Percentage_of_Hot_Region>
			<Generated_Aligned_Addresses>true</Generated_Aligned_Addresses>
			<Address_Alignment_Unit>8</Address_Alignment_Unit>
			<Request_Size_Distribution>FIXED</Request_Size_Distribution>
			<Average_Request_Size>${request_size}</Average_Request_Size>
			<Variance_Request_Size>0</Variance_Request_Size>
			<Seed>12345</Seed>
			<Average_No_of_Reqs_in_Queue>${queue_depth}</Average_No_of_Reqs_in_Queue>
			<Stop_Time>10000000000</Stop_Time>
			<Total_Requests_To_Generate>0</Total_Requests_To_Generate>
		</IO_Flow_Parameter_Set_Synthetic>
	</IO_Scenario>
</MQSim_IO_Scenarios>
EOF
}

# ============================================================================
# Trace-based Workload 생성 함수 (TPCC)
# ============================================================================
generate_trace_workload() {
    local output_file=$1
    local trace_file=$2
    local channel_count=$3
    local chip_count=$4
    
    local channel_ids=""
    for ((i=0; i<channel_count; i++)); do
        [ $i -eq 0 ] && channel_ids="$i" || channel_ids="${channel_ids},$i"
    done
    
    local chip_ids=""
    for ((i=0; i<chip_count; i++)); do
        [ $i -eq 0 ] && chip_ids="$i" || chip_ids="${chip_ids},$i"
    done
    
    cat > "${output_file}" << EOF
<?xml version="1.0" encoding="us-ascii"?>
<MQSim_IO_Scenarios>
	<IO_Scenario>
		<IO_Flow_Parameter_Set_Trace_Based>
			<Priority_Class>HIGH</Priority_Class>
			<Device_Level_Data_Caching_Mode>WRITE_CACHE</Device_Level_Data_Caching_Mode>
			<Channel_IDs>${channel_ids}</Channel_IDs>
			<Chip_IDs>${chip_ids}</Chip_IDs>
			<Die_IDs>0,1</Die_IDs>
			<Plane_IDs>0,1</Plane_IDs>
			<Initial_Occupancy_Percentage>70</Initial_Occupancy_Percentage>
			<File_Path>${trace_file}</File_Path>
			<Percentage_To_Be_Executed>100</Percentage_To_Be_Executed>
			<Relay_Count>1</Relay_Count>
			<Time_Unit>NANOSECOND</Time_Unit>
		</IO_Flow_Parameter_Set_Trace_Based>
	</IO_Scenario>
</MQSim_IO_Scenarios>
EOF
}

# ============================================================================
# 실험 실행 함수
# ============================================================================
run_single_experiment() {
    local exp_name=$1
    local ssd_config=$2
    local workload_config=$3
    local result_subdir=$4
    
    local result_dir="${RESULTS_DIR}/${result_subdir}"
    mkdir -p "${result_dir}"
    
    echo "  [RUN] ${exp_name}"
    
    if ./MQSim -i "${ssd_config}" -w "${workload_config}" > "${result_dir}/${exp_name}.log" 2>&1; then
        # MQSim 출력 파일 이동
        for f in *_scenario_*.xml; do
            [ -f "$f" ] && mv "$f" "${result_dir}/${exp_name}_output.xml" 2>/dev/null
        done
        echo "    [OK] ${result_dir}/${exp_name}_output.xml"
    else
        echo "    [FAIL] See ${result_dir}/${exp_name}.log"
    fi
}

# ============================================================================
# Step 1: MQSim 빌드
# ============================================================================
echo "============================================"
echo "Step 1: Building MQSim"
echo "============================================"
make clean 2>/dev/null || true
make -j$(nproc)

if [ !  -f "./MQSim" ]; then
    echo "[ERROR] MQSim build failed"
    exit 1
fi
echo "[OK] MQSim build complete"
echo ""

# ============================================================================
# 실험 1: IO_Queue_Depth 변화 (Host Queueing Bottleneck)
# 
# IO_Queue_Depth: SSD NVMe submission/completion queue의 물리적 크기
# Workload Queue Depth: 높은 값(512)으로 고정하여 SSD 큐를 포화시킴
# ============================================================================
echo "============================================"
echo "Experiment 1: IO_Queue_Depth (Host Queueing)"
echo "============================================"

for io_qd in "${IO_QUEUE_DEPTHS[@]}"; do
    echo "[EXP1] IO_Queue_Depth=${io_qd}"
    
    ssd_cfg="${CONFIGS_DIR}/ssd_ioqd${io_qd}.xml"
    generate_ssd_config "${ssd_cfg}" \
        "${io_qd}" \
        "${BASELINE_DATA_CACHE_CAPACITY}" \
        "${BASELINE_FLASH_CHANNEL_COUNT}" \
        "${BASELINE_CHIP_NO_PER_CHANNEL}"
    
    # 4KB Random Read
    echo "4KB Random Read IO_Queue_Depth=${io_qd}"
    wl="${WORKLOADS_DIR}/wl_ioqd${io_qd}_4kb_randread.xml"
    generate_synthetic_workload "${wl}" 100 8 "RANDOM_UNIFORM" "${io_qd}" \
        "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
    run_single_experiment "ioqd${io_qd}_4kb_randread" "${ssd_cfg}" "${wl}" "exp1_io_queue_depth"
    
#    # 4KB Random Write
#    echo "4KB Random Write IO_Queue_Depth=${io_qd}"
#    wl="${WORKLOADS_DIR}/wl_ioqd${io_qd}_4kb_randwrite.xml"
#    generate_synthetic_workload "${wl}" 0 8 "RANDOM_UNIFORM" "${io_qd}" \
#        "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
#    run_single_experiment "ioqd${io_qd}_4kb_randwrite" "${ssd_cfg}" "${wl}" "exp1_io_queue_depth"
#    
    # 4KB Mixed 70/30
    echo "4KB Mixed 70/30 IO_Queue_Depth=${io_qd}"
    wl="${WORKLOADS_DIR}/wl_ioqd${io_qd}_4kb_mixed.xml"
    generate_synthetic_workload "${wl}" 70 8 "RANDOM_UNIFORM" "${io_qd}" \
        "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
    run_single_experiment "ioqd${io_qd}_4kb_mixed" "${ssd_cfg}" "${wl}" "exp1_io_queue_depth"
    
    # 128KB Sequential Read
    echo "128KB Sequential Read IO_Queue_Depth=${io_qd}"
    wl="${WORKLOADS_DIR}/wl_ioqd${io_qd}_128kb_seqread.xml"
    generate_synthetic_workload "${wl}" 100 256 "STREAMING" "${io_qd}" \
        "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
    run_single_experiment "ioqd${io_qd}_128kb_seqread" "${ssd_cfg}" "${wl}" "exp1_io_queue_depth"
    
    # 128KB Sequential Write
    echo "128KB Sequential Write IO_Queue_Depth=${io_qd}"
    wl="${WORKLOADS_DIR}/wl_ioqd${io_qd}_128kb_seqwrite.xml"
    generate_synthetic_workload "${wl}" 0 256 "STREAMING" "${io_qd}" \
        "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
    run_single_experiment "ioqd${io_qd}_128kb_seqwrite" "${ssd_cfg}" "${wl}" "exp1_io_queue_depth"

    if [ -f "${TRACE_FILE}" ]; then
        echo "TPCC with IO_Queue_Depth=${io_qd}"
	wl="${WORKLOADS_DIR}/wl_tpcc_ioqd${io_qd}.xml"
        generate_trace_workload "${wl}" "${TRACE_FILE}" \
            "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
        run_single_experiment "tpcc_ioqd${io_qd}" "${ssd_cfg}" "${wl}" "exp4_tpcc"
    fi

done
echo ""

# ============================================================================
# 실험 2: Data_Cache_Capacity 변화 (DRAM Buffering Bottleneck)
# ============================================================================
echo "============================================"
echo "Experiment 2: Data_Cache_Capacity (DRAM)"
echo "============================================"

for i in "${! DATA_CACHE_CAPACITIES[@]}"; do
    cache_cap="${DATA_CACHE_CAPACITIES[$i]}"
    cache_label="${DATA_CACHE_LABELS[$i]}"
    
    echo "[EXP2] Data_Cache_Capacity=${cache_label}"
    
    ssd_cfg="${CONFIGS_DIR}/ssd_cache${cache_label}.xml"
    generate_ssd_config "${ssd_cfg}" \
        "${BASELINE_IO_QUEUE_DEPTH}" \
        "${cache_cap}" \
        "${BASELINE_FLASH_CHANNEL_COUNT}" \
        "${BASELINE_CHIP_NO_PER_CHANNEL}"
    
    # 4KB Random Read
    echo "4KB Random Read with Cache=${cache_label}"
    wl="${WORKLOADS_DIR}/wl_cache${cache_label}_4kb_randread.xml"
    generate_synthetic_workload "${wl}" 100 8 "RANDOM_UNIFORM" "${WORKLOAD_QUEUE_DEPTH}" \
        "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
    run_single_experiment "cache${cache_label}_4kb_randread" "${ssd_cfg}" "${wl}" "exp2_data_cache"
    
#    # 4KB Random Write
#    echo "4KB Random Write with Cache=${cache_label}"
#    wl="${WORKLOADS_DIR}/wl_cache${cache_label}_4kb_randwrite.xml"
#    generate_synthetic_workload "${wl}" 0 8 "RANDOM_UNIFORM" "${WORKLOAD_QUEUE_DEPTH}" \
#        "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
#    run_single_experiment "cache${cache_label}_4kb_randwrite" "${ssd_cfg}" "${wl}" "exp2_data_cache"
#    
    # 4KB Mixed 70/30
    echo "4KB Mixed 70/30 with Cache=${cache_label}"
    wl="${WORKLOADS_DIR}/wl_cache${cache_label}_4kb_mixed.xml"
    generate_synthetic_workload "${wl}" 70 8 "RANDOM_UNIFORM" "${WORKLOAD_QUEUE_DEPTH}" \
        "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
    run_single_experiment "cache${cache_label}_4kb_mixed" "${ssd_cfg}" "${wl}" "exp2_data_cache"
    
    # 128KB Sequential Read
    echo "128KB Sequential Read with Cache=${cache_label}"
    wl="${WORKLOADS_DIR}/wl_cache${cache_label}_128kb_seqread.xml"
    generate_synthetic_workload "${wl}" 100 256 "STREAMING" "${WORKLOAD_QUEUE_DEPTH}" \
        "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
    run_single_experiment "cache${cache_label}_128kb_seqread" "${ssd_cfg}" "${wl}" "exp2_data_cache"
    
    # 128KB Sequential Write
    echo "128KB Sequential Write with Cache=${cache_label}"
    wl="${WORKLOADS_DIR}/wl_cache${cache_label}_128kb_seqwrite.xml"
    generate_synthetic_workload "${wl}" 0 256 "STREAMING" "${WORKLOAD_QUEUE_DEPTH}" \
        "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
    run_single_experiment "cache${cache_label}_128kb_seqwrite" "${ssd_cfg}" "${wl}" "exp2_data_cache"

    if [ -f "${TRACE_FILE}" ]; then
        echo "TPCC with Cache=${cache_label}"
	wl="${WORKLOADS_DIR}/wl_tpcc_cache${cache_label}.xml"
        generate_trace_workload "${wl}" "${TRACE_FILE}" \
            "${BASELINE_FLASH_CHANNEL_COUNT}" "${BASELINE_CHIP_NO_PER_CHANNEL}"
        run_single_experiment "tpcc_cache${cache_label}" "${ssd_cfg}" "${wl}" "exp4_tpcc"
    fi

done
echo ""

# ============================================================================
# 실험 3: Flash Parallelism 변화 (Backend Bottleneck)
# ============================================================================
echo "============================================"
echo "Experiment 3: Flash Parallelism (Backend)"
echo "============================================"

for ch_cnt in "${FLASH_CHANNEL_COUNTS[@]}"; do
    for chip_cnt in "${CHIP_NO_PER_CHANNELS[@]}"; do
        total_ways=$((ch_cnt * chip_cnt))
        echo "[EXP3] Channels=${ch_cnt}, Chips/Ch=${chip_cnt} (Total=${total_ways} ways)"
        
        ssd_cfg="${CONFIGS_DIR}/ssd_ch${ch_cnt}_chip${chip_cnt}.xml"
        generate_ssd_config "${ssd_cfg}" \
            "${BASELINE_IO_QUEUE_DEPTH}" \
            "${BASELINE_DATA_CACHE_CAPACITY}" \
            "${ch_cnt}" \
            "${chip_cnt}"
        
        # 4KB Random Read
	echo "4KB Random Read with Channels=${ch_cnt}, Chips/Ch=${chip_cnt} (Total=${total_ways} ways)"
        wl="${WORKLOADS_DIR}/wl_ch${ch_cnt}_chip${chip_cnt}_4kb_randread.xml"
        generate_synthetic_workload "${wl}" 100 8 "RANDOM_UNIFORM" "${WORKLOAD_QUEUE_DEPTH}" "${ch_cnt}" "${chip_cnt}"
        run_single_experiment "ch${ch_cnt}_chip${chip_cnt}_4kb_randread" "${ssd_cfg}" "${wl}" "exp3_flash_parallelism"
        
#        # 4KB Random Write
#	echo "4KB Random Write with Channels=${ch_cnt}, Chips/Ch=${chip_cnt} (Total=${total_ways} ways)"
#        wl="${WORKLOADS_DIR}/wl_ch${ch_cnt}_chip${chip_cnt}_4kb_randwrite.xml"
#        generate_synthetic_workload "${wl}" 0 8 "RANDOM_UNIFORM" "${WORKLOAD_QUEUE_DEPTH}" "${ch_cnt}" "${chip_cnt}"
#        run_single_experiment "ch${ch_cnt}_chip${chip_cnt}_4kb_randwrite" "${ssd_cfg}" "${wl}" "exp3_flash_parallelism"
#        
        # 4KB Mixed 70/30
	echo "4KB Mixed 70/30 with Channels=${ch_cnt}, Chips/Ch=${chip_cnt} (Total=${total_ways} ways)"
        wl="${WORKLOADS_DIR}/wl_ch${ch_cnt}_chip${chip_cnt}_4kb_mixed.xml"
        generate_synthetic_workload "${wl}" 70 8 "RANDOM_UNIFORM" "${WORKLOAD_QUEUE_DEPTH}" "${ch_cnt}" "${chip_cnt}"
        run_single_experiment "ch${ch_cnt}_chip${chip_cnt}_4kb_mixed" "${ssd_cfg}" "${wl}" "exp3_flash_parallelism"
        
        # 128KB Sequential Read
	echo "128KB Sequential Read with Channels=${ch_cnt}, Chips/Ch=${chip_cnt} (Total=${total_ways} ways)"
        wl="${WORKLOADS_DIR}/wl_ch${ch_cnt}_chip${chip_cnt}_128kb_seqread.xml"
        generate_synthetic_workload "${wl}" 100 256 "STREAMING" "${WORKLOAD_QUEUE_DEPTH}" "${ch_cnt}" "${chip_cnt}"
        run_single_experiment "ch${ch_cnt}_chip${chip_cnt}_128kb_seqread" "${ssd_cfg}" "${wl}" "exp3_flash_parallelism"
        
        # 128KB Sequential Write
	echo "128KB Sequential Write with Channels=${ch_cnt}, Chips/Ch=${chip_cnt} (Total=${total_ways} ways)"
        wl="${WORKLOADS_DIR}/wl_ch${ch_cnt}_chip${chip_cnt}_128kb_seqwrite.xml"
        generate_synthetic_workload "${wl}" 0 256 "STREAMING" "${WORKLOAD_QUEUE_DEPTH}" "${ch_cnt}" "${chip_cnt}"
        run_single_experiment "ch${ch_cnt}_chip${chip_cnt}_128kb_seqwrite" "${ssd_cfg}" "${wl}" "exp3_flash_parallelism"

	if [ -f "${TRACE_FILE}" ]; then
		echo "TPCC with Channels=${ch_cnt}, Chips/Ch=${chip_cnt} (Total=${total_ways} ways)"
		wl="${WORKLOADS_DIR}/wl_tpcc_ch${ch_cnt}_chip${chip_cnt}.xml"
		generate_trace_workload "${wl}" "${TRACE_FILE}" "${ch_cnt}" "${chip_cnt}"
		run_single_experiment "tpcc_ch${ch_cnt}_chip${chip_cnt}" "${ssd_cfg}" "${wl}" "exp4_tpcc"
	fi
    done
done
echo ""

# ============================================================================
# 완료
# ============================================================================
echo "============================================"
echo "All experiments completed!"
echo "Results: ${RESULTS_DIR}/"
echo "============================================"
