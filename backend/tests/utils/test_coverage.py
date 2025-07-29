"""
Test coverage utilities and reporting
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import coverage
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CoverageReport:
    """Coverage report data"""
    total_statements: int
    covered_statements: int
    missing_statements: int
    coverage_percentage: float
    files: Dict[str, Dict[str, any]]
    timestamp: datetime
    
    @property
    def is_passing(self) -> bool:
        """Check if coverage meets minimum threshold"""
        return self.coverage_percentage >= 80.0


class CoverageAnalyzer:
    """Analyze and report test coverage"""
    
    def __init__(self, source_dir: str = "backend", min_coverage: float = 80.0):
        self.source_dir = source_dir
        self.min_coverage = min_coverage
        self.cov = coverage.Coverage(
            source=[source_dir],
            omit=[
                "*/tests/*",
                "*/migrations/*",
                "*/__pycache__/*",
                "*/venv/*",
                "*/env/*"
            ]
        )
    
    def start(self):
        """Start coverage measurement"""
        self.cov.start()
    
    def stop(self):
        """Stop coverage measurement"""
        self.cov.stop()
        self.cov.save()
    
    def analyze(self) -> CoverageReport:
        """Analyze coverage data"""
        self.cov.load()
        
        # Get coverage data
        total = 0
        covered = 0
        files_data = {}
        
        for filename in self.cov.get_data().measured_files():
            analysis = self.cov.analysis2(filename)
            
            file_total = len(analysis[1]) + len(analysis[3])
            file_covered = len(analysis[1])
            file_missing = len(analysis[3])
            
            total += file_total
            covered += file_covered
            
            files_data[filename] = {
                "statements": file_total,
                "covered": file_covered,
                "missing": file_missing,
                "missing_lines": analysis[3],
                "coverage": (file_covered / file_total * 100) if file_total > 0 else 100
            }
        
        coverage_percentage = (covered / total * 100) if total > 0 else 0
        
        return CoverageReport(
            total_statements=total,
            covered_statements=covered,
            missing_statements=total - covered,
            coverage_percentage=coverage_percentage,
            files=files_data,
            timestamp=datetime.now()
        )
    
    def generate_report(self, format: str = "html", output_dir: str = "htmlcov"):
        """Generate coverage report"""
        if format == "html":
            self.cov.html_report(directory=output_dir)
        elif format == "xml":
            self.cov.xml_report(outfile=f"{output_dir}/coverage.xml")
        elif format == "json":
            self.cov.json_report(outfile=f"{output_dir}/coverage.json")
    
    def find_uncovered_code(self) -> Dict[str, List[int]]:
        """Find all uncovered lines of code"""
        uncovered = {}
        
        for filename in self.cov.get_data().measured_files():
            analysis = self.cov.analysis2(filename)
            if analysis[3]:  # Missing lines
                uncovered[filename] = analysis[3]
        
        return uncovered
    
    def get_module_coverage(self, module_path: str) -> Optional[float]:
        """Get coverage for specific module"""
        for filename in self.cov.get_data().measured_files():
            if module_path in filename:
                analysis = self.cov.analysis2(filename)
                total = len(analysis[1]) + len(analysis[3])
                covered = len(analysis[1])
                return (covered / total * 100) if total > 0 else 100
        return None
    
    def generate_badge(self, output_path: str = "coverage_badge.svg"):
        """Generate coverage badge SVG"""
        report = self.analyze()
        percentage = report.coverage_percentage
        
        # Determine color based on coverage
        if percentage >= 90:
            color = "#4c1"  # Bright green
        elif percentage >= 80:
            color = "#97ca00"  # Green
        elif percentage >= 70:
            color = "#a4a61d"  # Yellow-green
        elif percentage >= 60:
            color = "#dfb317"  # Yellow
        else:
            color = "#e05d44"  # Red
        
        # SVG template
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" width="114" height="20">
            <linearGradient id="b" x2="0" y2="100%">
                <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
                <stop offset="1" stop-opacity=".1"/>
            </linearGradient>
            <mask id="a">
                <rect width="114" height="20" rx="3" fill="#fff"/>
            </mask>
            <g mask="url(#a)">
                <path fill="#555" d="M0 0h63v20H0z"/>
                <path fill="{color}" d="M63 0h51v20H63z"/>
                <path fill="url(#b)" d="M0 0h114v20H0z"/>
            </g>
            <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                <text x="31.5" y="15" fill="#010101" fill-opacity=".3">coverage</text>
                <text x="31.5" y="14">coverage</text>
                <text x="87.5" y="15" fill="#010101" fill-opacity=".3">{percentage:.1f}%</text>
                <text x="87.5" y="14">{percentage:.1f}%</text>
            </g>
        </svg>
        """.strip()
        
        with open(output_path, "w") as f:
            f.write(svg)


class CoverageDiff:
    """Compare coverage between runs"""
    
    def __init__(self, baseline_path: str, current_path: str):
        self.baseline_path = baseline_path
        self.current_path = current_path
    
    def compare(self) -> Dict[str, any]:
        """Compare coverage reports"""
        with open(self.baseline_path) as f:
            baseline = json.load(f)
        
        with open(self.current_path) as f:
            current = json.load(f)
        
        baseline_coverage = baseline["totals"]["percent_covered"]
        current_coverage = current["totals"]["percent_covered"]
        
        diff = {
            "baseline_coverage": baseline_coverage,
            "current_coverage": current_coverage,
            "difference": current_coverage - baseline_coverage,
            "improved": current_coverage > baseline_coverage,
            "files_improved": [],
            "files_regressed": [],
            "new_files": [],
            "removed_files": []
        }
        
        baseline_files = set(baseline["files"].keys())
        current_files = set(current["files"].keys())
        
        # Find new and removed files
        diff["new_files"] = list(current_files - baseline_files)
        diff["removed_files"] = list(baseline_files - current_files)
        
        # Compare common files
        for file in baseline_files & current_files:
            baseline_file_coverage = baseline["files"][file]["summary"]["percent_covered"]
            current_file_coverage = current["files"][file]["summary"]["percent_covered"]
            
            if current_file_coverage > baseline_file_coverage:
                diff["files_improved"].append({
                    "file": file,
                    "baseline": baseline_file_coverage,
                    "current": current_file_coverage,
                    "improvement": current_file_coverage - baseline_file_coverage
                })
            elif current_file_coverage < baseline_file_coverage:
                diff["files_regressed"].append({
                    "file": file,
                    "baseline": baseline_file_coverage,
                    "current": current_file_coverage,
                    "regression": baseline_file_coverage - current_file_coverage
                })
        
        return diff


def generate_coverage_report_md(report: CoverageReport, output_path: str = "coverage_report.md"):
    """Generate markdown coverage report"""
    content = f"""# Test Coverage Report

Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

## Summary

- **Total Coverage**: {report.coverage_percentage:.2f}%
- **Total Statements**: {report.total_statements:,}
- **Covered Statements**: {report.covered_statements:,}
- **Missing Statements**: {report.missing_statements:,}
- **Status**: {"✅ PASSING" if report.is_passing else "❌ FAILING"}

## File Coverage

| File | Coverage | Statements | Missing |
|------|----------|------------|---------|
"""
    
    # Sort files by coverage percentage
    sorted_files = sorted(
        report.files.items(),
        key=lambda x: x[1]["coverage"],
        reverse=True
    )
    
    for filepath, data in sorted_files:
        # Make path relative
        rel_path = filepath.replace(os.getcwd() + "/", "")
        coverage_pct = data["coverage"]
        
        # Add emoji indicator
        if coverage_pct >= 90:
            indicator = "🟢"
        elif coverage_pct >= 80:
            indicator = "🟡"
        else:
            indicator = "🔴"
        
        content += f"| {indicator} {rel_path} | {coverage_pct:.1f}% | {data['statements']} | {data['missing']} |\n"
    
    # Add uncovered lines section
    content += "\n## Uncovered Lines\n\n"
    
    files_with_missing = [
        (f, d) for f, d in report.files.items() 
        if d["missing_lines"]
    ]
    
    if files_with_missing:
        for filepath, data in sorted(files_with_missing, key=lambda x: len(x[1]["missing_lines"]), reverse=True)[:10]:
            rel_path = filepath.replace(os.getcwd() + "/", "")
            content += f"### {rel_path}\n"
            content += f"Missing lines: {', '.join(map(str, data['missing_lines'][:20]))}"
            if len(data['missing_lines']) > 20:
                content += f" ... and {len(data['missing_lines']) - 20} more"
            content += "\n\n"
    else:
        content += "No uncovered lines! 🎉\n"
    
    with open(output_path, "w") as f:
        f.write(content)


# Pytest plugin for coverage
def pytest_configure(config):
    """Configure coverage for pytest"""
    config.addinivalue_line(
        "markers",
        "coverage: mark test to be included in coverage report"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection for coverage"""
    # Add coverage marker to all tests by default
    for item in items:
        item.add_marker(pytest.mark.coverage)