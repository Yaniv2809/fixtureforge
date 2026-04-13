"""
Data Streamer - The heart of Lazy Evaluation.
Handles writing data incrementally to avoid Memory Explosion.
"""
import csv
import json
from pathlib import Path
from typing import  Any
from pydantic import BaseModel

class DataStreamer:
    def __init__(self, filename: str):
        self.path = Path(filename)
        self.extension = self.path.suffix.lower()
        self.file_handle = None
        self.writer = None
        self.first_item = True
        self.is_open = False

    def start(self):
        """Opens the file stream"""
        self.file_handle = open(self.path, "w", encoding="utf-8", newline="")
        self.is_open = True
        
        if self.extension == ".json":
            self.file_handle.write("[\n")  # Start of JSON array
        elif self.extension == ".sql":
            self.file_handle.write("-- Auto-generated Stream by FixtureForge\n")

    def write(self, item: Any):
        """Writes a single item to the stream"""
        if not self.is_open:
            raise RuntimeError("Stream is not open. Call start() first.")

        data = item.model_dump() if isinstance(item, BaseModel) else item.__dict__

        if self.extension == ".json":
            self._write_json_item(data)
        elif self.extension == ".csv":
            self._write_csv_item(data)
        elif self.extension == ".sql":
            self._write_sql_item(data, item)

    def close(self):
        """Closes the stream properly"""
        if self.extension == ".json":
            self.file_handle.write("\n]")  # End of JSON array
        
        if self.file_handle:
            self.file_handle.close()
        self.is_open = False
        print(f"✅ Stream closed. Data saved to {self.path}")

    def _write_json_item(self, data: dict):
        if not self.first_item:
            self.file_handle.write(",\n")
        json_str = json.dumps(data, default=str, indent=2)
        # Indent the internal lines to make it valid pretty JSON
        self.file_handle.write(json_str)
        self.first_item = False

    def _write_csv_item(self, data: dict):
        if self.first_item:
            self.writer = csv.DictWriter(self.file_handle, fieldnames=data.keys())
            self.writer.writeheader()
        
        self.writer.writerow(data)
        self.first_item = False

    def _write_sql_item(self, data: dict, original_obj: Any):
        table_name = original_obj.__class__.__name__.lower() + "s"
        columns = ", ".join(data.keys())
        values = []
        
        for v in data.values():
            if v is None:
                values.append("NULL")
            else:
                clean_v = str(v).replace("'", "''")
                values.append(f"'{clean_v}'")
        
        vals_str = ", ".join(values)
        self.file_handle.write(f"INSERT INTO {table_name} ({columns}) VALUES ({vals_str});\n")