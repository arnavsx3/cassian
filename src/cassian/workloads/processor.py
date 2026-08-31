from cassian.domain.models import JobView


class WorkloadProcessor:
    MODULUS = 1_000_000_007

    def process_chunk(self, job: JobView) -> JobView:
        start_record = job.processed_records
        end_record = min(start_record + job.chunk_size, job.total_records)

        if start_record >= end_record:
            job.progress_percent = self._progress_percent(
                job.processed_records, job.total_records
            )
            return job

        job.result_checksum = self.fold_records(
            start_record=start_record,
            end_record=end_record,
            initial_checksum=job.result_checksum,
        )
        job.processed_records = end_record
        job.last_checkpoint_records = end_record
        job.checkpoint_count += 1
        job.progress_percent = self._progress_percent(
            job.processed_records, job.total_records
        )
        return job

    def full_checksum(self, total_records: int) -> int:
        return self.fold_records(
            start_record=0,
            end_record=total_records,
            initial_checksum=0,
        )

    def fold_records(
        self,
        *,
        start_record: int,
        end_record: int,
        initial_checksum: int,
    ) -> int:
        checksum = initial_checksum

        for record_number in range(start_record + 1, end_record + 1):
            transformed = ((record_number * 31) ^ (record_number >> 3)) % self.MODULUS
            checksum = (checksum + transformed) % self.MODULUS

        return checksum

    def _progress_percent(self, processed_records: int, total_records: int) -> float:
        return round((processed_records / total_records) * 100, 2)
