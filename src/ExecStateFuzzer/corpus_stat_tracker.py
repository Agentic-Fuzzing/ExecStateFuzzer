from .models import ExecutionResult, CorpusStatResult
import time
import threading

class CorpusStatTracker:
    def __init__(self, MAP_SIZE: int, config: dict):
        self.MAP_SIZE = MAP_SIZE
        self.cov_bitmap = bytearray(MAP_SIZE)
        self.branch_taken = bytearray(MAP_SIZE)
        self.branch_fallthrough = bytearray(MAP_SIZE)
        self.instruction_addresses: set[int] = set()
        self.total_instructions = 0
        self.pathlen_blocks_sum = 0
        self.pathlen_blocks_max = 0
        self.calldepth_inside_sum = 0
        self.calldepth_inside_max = 0
        self.num_samples = 0
        
        # Coverage plateau tracking
        self.coverage_plateau_timeout = config['coverage_plateau_timeout_seconds']
        self.last_coverage_time = time.time()
        self.last_coverage_edges = 0
    
        self.start_time = time.time()
        self.cumulative_execution_time = 0.0
        self._running = False
        self._lock = threading.Lock()
        self._snapshot_thread = None
    
    def add_sample(self, sample: ExecutionResult) -> None:
        new_edge_coverage = False
      
        if sample.cov_bitmap is not None:
            gb = self.cov_bitmap
            rb = sample.cov_bitmap
            for i in range(len(gb)):
                # new edge coverage
                if rb[i] and not gb[i]:
                    gb[i] = 1
                    new_edge_coverage = True
        if sample.branch_taken_bitmap is not None and sample.branch_fallthrough_bitmap is not None:
            for i in range(self.MAP_SIZE):
                if sample.branch_taken_bitmap[i]:
                    self.branch_taken[i] = 1
                if sample.branch_fallthrough_bitmap[i]:
                    self.branch_fallthrough[i] = 1
        if sample.instr_address_set:
            self.instruction_addresses.update(sample.instr_address_set)
        
        if new_edge_coverage:
            self.reset_time_since_last_coverage()
        
        self.total_instructions += sample.total_instructions
        self.pathlen_blocks_sum += sample.pathlen_blocks
        self.pathlen_blocks_max = max(self.pathlen_blocks_max, sample.pathlen_blocks)
        self.calldepth_inside_sum += sample.call_depth
        self.calldepth_inside_max = max(self.calldepth_inside_max, sample.call_depth)
        self.cumulative_execution_time += sample.execution_time

        self.num_samples += 1

    def get_result(self) -> CorpusStatResult:
        return CorpusStatResult(
            total_edges=sum(1 for b in self.cov_bitmap if b),
            total_branch_sites=sum(1 for bt, bf in zip(self.branch_taken, self.branch_fallthrough) if bt or bf),
            total_unique_instructions=len(self.instruction_addresses),
            avg_pathlen_blocks=self.pathlen_blocks_sum / self.num_samples,
            max_pathlen_blocks=self.pathlen_blocks_max,
            avg_calldepth=self.calldepth_inside_sum / self.num_samples,
            max_calldepth=self.calldepth_inside_max,
        )
    
    def is_coverage_plateau(self) -> bool:
        current_time = time.time()
        time_since_last_coverage = current_time - self.last_coverage_time
        
        if time_since_last_coverage >= self.coverage_plateau_timeout:
            return True
        
        return False
    
    def reset_time_since_last_coverage(self) -> None:
        self.last_coverage_time = time.time()