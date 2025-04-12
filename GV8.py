import re
import json
import os
import logging
import asyncio
import aiohttp
from jira import JIRA, JIRAError
import customtkinter as ctk
from tkinter import filedialog, messagebox, scrolledtext
from threading import RLock, Lock, Thread, Event
import queue
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import time
import pickle
import sys
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from PIL import Image, ImageTk

try:
    import enchant
    SPELLCHECK_AVAILABLE = True
except ImportError:
    SPELLCHECK_AVAILABLE = False
    logging.warning("Enchant module not available. Install with 'pip install pyenchant'.")

# Helper function to resolve resource paths for PyInstaller
def resource_path(relative_path):
    """Get the absolute path to a resource, works for both development and PyInstaller executable."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    
    full_path = os.path.join(base_path, relative_path)
    logging.debug(f"Resolved resource path: {relative_path} -> {full_path}")
    return full_path

# Determine a safe directory for the log file
if getattr(sys, 'frozen', False):
    log_dir = os.path.dirname(sys.executable)
else:
    log_dir = os.path.dirname(os.path.abspath(__file__))

os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'gherkin-checker.log')

# Setup logging with more detailed output
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s'
)

class TestReport:
    """Class to generate and store analysis reports for Gherkin files."""
    def __init__(self, enabled_checks=None):
        self.issues = []
        self.misspelled_words = []
        self.stats = {"total_lines": 0, "scenarios": 0, "steps": 0, "total_iterations": 0}
        self.timestamp = time.strftime('%Y-%m-%d %I:%M:%S %p')
        self.filename = ""
        self.feature_type = "standard"
        self.enabled_checks = enabled_checks or {
            "syntax": True,
            "misspelled": True,
            "placeholder_mismatch": True,
            "placeholder_order": True,
            "invalid_placeholder": True,
            "repeated_word": True,
            "drive_cycle": True,
            "success_criteria": True,
            "duplicate_scenario": True
        }

    def add_issue(self, issue_type, description, line_num):
        self.issues.append((issue_type, description, line_num))

    def add_misspelled(self, word, line_num, suggestions):
        self.misspelled_words.append((word, line_num, suggestions))

    def update_stats(self, total_lines, scenarios, steps, total_iterations):
        self.stats.update({
            "total_lines": total_lines,
            "scenarios": scenarios,
            "steps": steps,
            "total_iterations": total_iterations
        })

    def set_filename(self, filename):
        self.filename = filename

    def set_feature_type(self, feature_type):
        self.feature_type = feature_type

    def get_total_errors(self):
        total = 0
        if self.enabled_checks["misspelled"]:
            total += len(self.misspelled_words)
        if self.enabled_checks["syntax"]:
            total += len([i for i in self.issues if i[0] == "Syntax Error"])
        if self.enabled_checks["placeholder_mismatch"]:
            total += len([i for i in self.issues if i[0] == "Placeholder Mismatch"])
        if self.enabled_checks["placeholder_order"]:
            total += len([i for i in self.issues if i[0] == "Placeholder Order"])
        if self.enabled_checks["invalid_placeholder"]:
            total += len([i for i in self.issues if i[0] == "Invalid Placeholder Syntax"])
        if self.enabled_checks["repeated_word"]:
            total += len([i for i in self.issues if i[0] == "Repeated Word"])
        if self.enabled_checks["drive_cycle"] and self.feature_type == "drive_cycle":
            total += len([i for i in self.issues if i[0] == "Syntax Error" and "Drive Cycle" in i[1]])
        if self.enabled_checks["success_criteria"] and self.feature_type == "success_criteria":
            total += len([i for i in self.issues if i[0] == "Syntax Error" and "Success Criteria" in i[1]])
        if self.enabled_checks["duplicate_scenario"]:
            total += len([i for i in self.issues if i[0] == "Duplicate Scenario"])
        return total

    def generate_report(self, format="text"):
        if format == "text":
            total_errors = self.get_total_errors()
            content = (
                f"Gherkin Feature File Analysis Report\nGenerated: {self.timestamp}\nAnalyzed File: {self.filename}\n"
                f"Total Errors Found: {total_errors}\n{'-' * 50}\n\n"
            )

            if self.enabled_checks["misspelled"]:
                content += (
                    f"Misspelled Words:\n" + (" - None found\n" if not self.misspelled_words else
                    "\n".join(f" - Line {ln}: '{w}' [Suggestions: {', '.join(s)}]" for w, ln, s in self.misspelled_words)) + "\n\n"
                )

            if self.enabled_checks["syntax"]:
                syntax_errors = [i for i in self.issues if i[0] == "Syntax Error"]
                content += (
                    f"Syntax Errors:\n" + (" - None found\n" if not syntax_errors else
                    "\n".join(f" - Line {i[2]}: {i[1]}" for i in syntax_errors)) + "\n\n"
                )

            if self.enabled_checks["placeholder_mismatch"]:
                placeholder_mismatches = [i for i in self.issues if i[0] == "Placeholder Mismatch"]
                content += (
                    f"Placeholder Mismatch Check:\n" + (" - None found\n" if not placeholder_mismatches else
                    "\n".join(f" - Line {i[2]}: {i[1]}" for i in placeholder_mismatches)) + "\n\n"
                )

            if self.enabled_checks["placeholder_order"]:
                placeholder_orders = [i for i in self.issues if i[0] == "Placeholder Order"]
                content += (
                    f"Placeholder Order Check:\n" + (" - None found\n" if not placeholder_orders else
                    "\n".join(f" - Line {i[2]}: {i[1]}" for i in placeholder_orders)) + "\n\n"
                )

            if self.enabled_checks["invalid_placeholder"]:
                invalid_placeholders = [i for i in self.issues if i[0] == "Invalid Placeholder Syntax"]
                content += (
                    f"Invalid Placeholder Syntax Check:\n" + (" - None found\n" if not invalid_placeholders else
                    "\n".join(f" - Line {i[2]}: {i[1]}" for i in invalid_placeholders)) + "\n\n"
                )

            if self.enabled_checks["repeated_word"]:
                repeated_words = [i for i in self.issues if i[0] == "Repeated Word"]
                content += (
                    f"Repeated Word Check:\n" + (" - None found\n" if not repeated_words else
                    "\n".join(f" - Line {i[2]}: {i[1]}" for i in repeated_words)) + "\n\n"
                )

            if self.enabled_checks["drive_cycle"] and self.feature_type == "drive_cycle":
                drive_cycle_errors = [i for i in self.issues if i[0] == "Syntax Error" and "Drive Cycle" in i[1]]
                content += (
                    f"Drive Cycle Format Check:\n" + (" - None found\n" if not drive_cycle_errors else
                    "\n".join(f" - Line {i[2]}: {i[1]}" for i in drive_cycle_errors)) + "\n\n"
                )

            if self.enabled_checks["success_criteria"] and self.feature_type == "success_criteria":
                success_criteria_errors = [i for i in self.issues if i[0] == "Syntax Error" and "Success Criteria" in i[1]]
                content += (
                    f"Success Criteria Format Check:\n" + (" - None found\n" if not success_criteria_errors else
                    "\n".join(f" - Line {i[2]}: {i[1]}" for i in success_criteria_errors)) + "\n\n"
                )

            if self.enabled_checks["duplicate_scenario"]:
                duplicate_scenarios = [i for i in self.issues if i[0] == "Duplicate Scenario"]
                content += (
                    f"Duplicate Scenario Check:\n" + (" - None found\n" if not duplicate_scenarios else
                    "\n".join(f" - Line {i[2]}: {i[1]}" for i in duplicate_scenarios)) + "\n\n"
                )

            content += (
                f"File Statistics:\n"
                f" - Total Lines: {self.stats['total_lines']}\n"
                f" - Scenarios: {self.stats['scenarios']}\n"
                f" - Steps: {self.stats['steps']}\n"
                f" - Total Iterations in Examples: {self.stats['total_iterations']}\n"
            )
            return content
        elif format == "json":
            return {
                "timestamp": self.timestamp,
                "filename": self.filename,
                "total_errors": self.get_total_errors(),
                "misspelled_words": [{"word": w, "line": ln, "suggestions": s} for w, ln, s in self.misspelled_words] if self.enabled_checks["misspelled"] else [],
                "syntax_errors": [{"line": i[2], "description": i[1]} for i in self.issues if i[0] == "Syntax Error"] if self.enabled_checks["syntax"] else [],
                "placeholder_mismatches": [{"line": i[2], "description": i[1]} for i in self.issues if i[0] == "Placeholder Mismatch"] if self.enabled_checks["placeholder_mismatch"] else [],
                "placeholder_orders": [{"line": i[2], "description": i[1]} for i in self.issues if i[0] == "Placeholder Order"] if self.enabled_checks["placeholder_order"] else [],
                "invalid_placeholders": [{"line": i[2], "description": i[1]} for i in self.issues if i[0] == "Invalid Placeholder Syntax"] if self.enabled_checks["invalid_placeholder"] else [],
                "repeated_words": [{"line": i[2], "description": i[1]} for i in self.issues if i[0] == "Repeated Word"] if self.enabled_checks["repeated_word"] else [],
                "drive_cycle_errors": [{"line": i[2], "description": i[1]} for i in self.issues if i[0] == "Syntax Error" and "Drive Cycle" in i[1]] if self.enabled_checks["drive_cycle"] and self.feature_type == "drive_cycle" else [],
                "success_criteria_errors": [{"line": i[2], "description": i[1]} for i in self.issues if i[0] == "Syntax Error" and "Success Criteria" in i[1]] if self.enabled_checks["success_criteria"] and self.feature_type == "success_criteria" else [],
                "duplicate_scenarios": [{"line": i[2], "description": i[1]} for i in self.issues if i[0] == "Duplicate Scenario"] if self.enabled_checks["duplicate_scenario"] else [],
                "stats": self.stats
            }
        else:
            raise ValueError(f"Unsupported report format: {format}")

class GherkinChecker:
    """Class to handle Gherkin file processing and validation."""
    def __init__(self, spellchecker=None, spell_cache=None, custom_words=None, spell_lock=None, feature_type="standard", spellcheck_enabled=True, spellcheck_language="en_UK"):
        self.spellchecker = spellchecker if spellchecker else (enchant.Dict(spellcheck_language) if SPELLCHECK_AVAILABLE else None)
        self.spell_cache = spell_cache or {}
        self.custom_words = custom_words or set()
        self.spell_lock = spell_lock or RLock()
        self.feature_type = feature_type
        self.spellcheck_enabled = spellcheck_enabled
        self.keyword_pattern = re.compile(r"\b(?:Feature|Scenario|Given|When|Then|And|But|Background|Scenario Outline)\b")
        self.word_pattern = re.compile(r"\b\w+\b")
        self.placeholder_pattern = re.compile(r'<"[^"]+">')
        self.fixed_value_pattern = re.compile(r'"[^"]*"')
        self.bad_placeholder_pattern = re.compile(r"'[^']*'")

    def process_file(self, file, report):
        report.set_feature_type(self.feature_type)
        try:
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except FileNotFoundError:
            logging.error(f"File not found: {file}")
            return False
        except UnicodeDecodeError:
            logging.error(f"Unable to decode file: {file}")
            return False

        scenarios = 0
        steps = 0
        total_iterations = 0
        scenario_dict = {}
        current_scenario = None
        current_steps = []
        in_examples = False
        examples_headers = None
        scenario_start_line = 0
        has_feature = False
        given_count = 0
        when_count = 0
        then_count = 0
        and_count = 0

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith("Feature"):
                has_feature = True
            elif line.startswith("Scenario"):
                if current_scenario and self.feature_type == "success_criteria":
                    logging.debug(f"Checking Success Criteria for scenario at line {scenario_start_line}: "
                                  f"Given={given_count}, When={when_count}, Then={then_count}, And={and_count}")
                    if given_count != 1:
                        report.add_issue("Syntax Error", f"Success Criteria must have exactly 1 Given, found {given_count}", scenario_start_line)
                    if when_count != 1:
                        report.add_issue("Syntax Error", f"Success Criteria must have exactly 1 When, found {when_count}", scenario_start_line)

                if not has_feature:
                    report.add_issue("Syntax Error", "Scenario found before Feature", i)
                scenarios += 1
                scenario_key = line
                if scenario_key in scenario_dict:
                    report.add_issue("Duplicate Scenario", f"Scenario identical to one at line {scenario_dict[scenario_key]}", i)
                else:
                    scenario_dict[scenario_key] = i
                current_scenario = line
                current_steps = []
                scenario_start_line = i
                given_count = 0
                when_count = 0
                then_count = 0
                and_count = 0
                in_examples = False
                examples_headers = None
            elif line.startswith("Examples"):
                if not current_scenario:
                    report.add_issue("Syntax Error", "Examples found outside a Scenario", i)
                in_examples = True
            elif in_examples and line.startswith('|'):
                if not examples_headers:
                    examples_headers = [h.strip() for h in line.split('|')[1:-1]]
                    placeholders_used = []
                    for step in current_steps:
                        placeholders = self.placeholder_pattern.findall(step)
                        placeholders_used.extend(placeholders)
                    for ph in set(placeholders_used):
                        placeholder_name = ph.strip('<>').strip('"')
                        if placeholder_name not in examples_headers:
                            step_index = next((idx for idx, step in enumerate(current_steps) if ph in step), -1)
                            report.add_issue(
                                "Placeholder Mismatch",
                                f"Placeholder '{ph}' does not match any column heading in the Examples table (case-sensitive)",
                                step_index + scenario_start_line if step_index != -1 else i
                            )
                    if placeholders_used:
                        header_order = {h: idx for idx, h in enumerate(examples_headers)}
                        last_pos = -1
                        for ph in placeholders_used:
                            placeholder_name = ph.strip('<>').strip('"')
                            current_pos = header_order.get(placeholder_name, -1)
                            if current_pos == -1:
                                continue
                            if current_pos < last_pos:
                                step_index = next((idx for idx, step in enumerate(current_steps) if ph in step), -1)
                                report.add_issue(
                                    "Placeholder Order",
                                    f"Placeholder '{ph}' used out of sequence relative to Examples table column headings",
                                    step_index + scenario_start_line if step_index != -1 else i
                                )
                            last_pos = max(last_pos, current_pos)
                else:
                    total_iterations += 1
            elif any(line.startswith(k) for k in ("Given", "When", "Then", "And", "But")):
                if not current_scenario:
                    report.add_issue("Syntax Error", "Step found outside a Scenario", i)
                steps += 1
                if current_scenario and not in_examples:
                    current_steps.append(line)
                if line.startswith("Given"):
                    given_count += 1
                    logging.debug(f"Incremented given_count to {given_count} at line {i}")
                elif line.startswith("When"):
                    when_count += 1
                    logging.debug(f"Incremented when_count to {when_count} at line {i}")
                elif line.startswith("Then"):
                    then_count += 1
                    logging.debug(f"Incremented then_count to {then_count} at line {i}")
                elif line.startswith("And"):
                    and_count += 1
                    logging.debug(f"Incremented and_count to {and_count} at line {i}")
                elif line.startswith("But"):
                    if self.feature_type == "drive_cycle":
                        report.add_issue("Syntax Error", "But not allowed in Drive Cycle format", i)
                    elif self.feature_type == "success_criteria":
                        report.add_issue("Syntax Error", "But not allowed in Success Criteria format", i)

            if (i == len(lines) or (line.startswith("Scenario") and current_scenario)) and current_scenario:
                if self.feature_type == "drive_cycle":
                    if when_count > 0:
                        report.add_issue("Syntax Error", "When not allowed in Drive Cycle format", scenario_start_line)
                    if then_count > 0:
                        report.add_issue("Syntax Error", "Then not allowed in Drive Cycle format", scenario_start_line)

            bad_placeholders = self.bad_placeholder_pattern.findall(line)
            for bp in bad_placeholders:
                bp_clean = bp.strip("'")
                if bp.startswith("'") and bp.endswith("'"):
                    report.add_issue(
                        "Invalid Placeholder Syntax",
                        f"Placeholder '{bp}' should use angle brackets with double quotes (e.g., <\"{bp_clean}\">) instead of single quotes",
                        i
                    )
                elif bp.startswith("'") and not bp.endswith("'"):
                    report.add_issue("Invalid Placeholder Syntax", f"Placeholder '{bp}' is missing a closing quote", i)
                elif bp.endswith("'") and not bp.startswith("'"):
                    report.add_issue("Invalid Placeholder Syntax", f"Placeholder '{bp}' is missing an opening quote", i)

            if self.spellcheck_enabled and self.spellchecker and not line.startswith('#'):
                cleaned_line = line
                cleaned_line = self.placeholder_pattern.sub('', cleaned_line)
                cleaned_line = self.fixed_value_pattern.sub('', cleaned_line)
                cleaned_line = cleaned_line.replace("'", "")
                words = self.word_pattern.findall(cleaned_line)
                words_to_check = {w.lower() for w in words if w not in ["Feature", "Scenario", "Given", "When", "Then", "And", "But", "Background", "Examples", "Scenario Outline"]}
                for word in words_to_check:
                    with self.spell_lock:
                        if word in self.spell_cache:
                            if self.spell_cache[word]:
                                report.add_misspelled(word, i, self.spell_cache[word])
                        elif word not in self.custom_words:
                            if not self.spellchecker.check(word):
                                suggestions = self.spellchecker.suggest(word)
                                report.add_misspelled(word, i, suggestions)
                                self.spell_cache[word] = suggestions
                            else:
                                self.spell_cache[word] = []

            if not (in_examples and line.startswith('|')):
                cleaned_line = line
                cleaned_line = self.placeholder_pattern.sub('', cleaned_line)
                cleaned_line = self.fixed_value_pattern.sub('', cleaned_line)
                words = self.word_pattern.findall(cleaned_line)
                for j in range(len(words) - 1):
                    if words[j] == words[j + 1] and words[j] not in ["Feature", "Scenario", "Given", "When", "Then", "And", "But", "Background", "Examples", "Scenario Outline"]:
                        report.add_issue("Repeated Word", f"Word '{words[j]}' repeated", i)

        if current_scenario and self.feature_type == "success_criteria":
            logging.debug(f"Final Success Criteria check for scenario at line {scenario_start_line}: "
                          f"Given={given_count}, When={when_count}, Then={then_count}, And={and_count}")
            if given_count != 1:
                report.add_issue("Syntax Error", f"Success Criteria must have exactly 1 Given, found {given_count}", scenario_start_line)
            if when_count != 1:
                report.add_issue("Syntax Error", f"Success Criteria must have exactly 1 When, found {when_count}", scenario_start_line)

        if not has_feature:
            report.add_issue("Syntax Error", "No Feature keyword found in file", 1)
        report.update_stats(len(lines), scenarios, steps, total_iterations)
        report.set_filename(file)
        return True

class GherkinCheckerApp:
    """Main application class for the Gherkin Checker GUI."""
    def __init__(self):
        self.config = self.load_config()
        self.root = ctk.CTk()
        self.root.minsize(600, 400)
        self.root.title("Gherkin Feature Checker")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.online_mode = False
        self.network_check_running = False
        self.spellcheck_enabled = True
        self.spellcheck_language = "en_UK"
        self.spellchecker = enchant.Dict(self.spellcheck_language) if SPELLCHECK_AVAILABLE else None
        if not SPELLCHECK_AVAILABLE:
            messagebox.showwarning("Warning", "Spellchecking unavailable. Install 'pyenchant' for British English spellcheck.")
        self.spell_cache = {}
        self.spell_cache_file = "spellcache.pkl"
        self.load_spell_cache()
        self.custom_words = set()
        self.spell_lock = RLock()
        self.feature_type = "standard"
        self.checker = GherkinChecker(
            self.spellchecker,
            self.spell_cache,
            self.custom_words,
            self.spell_lock,
            self.feature_type,
            self.spellcheck_enabled,
            self.spellcheck_language
        )
        self.task_queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=self.config["max_workers"])
        self.last_progress_update = 0
        self.progress_lock = Lock()
        self.jira_client = None
        self.pat = None
        self.username = None
        try:
            self.app_icon = ImageTk.PhotoImage(Image.open(resource_path("icons/app_icon.ico")))
        except Exception as e:
            logging.warning(f"Failed to load app_icon.ico for taskbar: {e}")
            self.app_icon = None
        self.setup_gui()
        self.load_saved_pat()  # Load saved credentials on startup
        self.loop = asyncio.new_event_loop()
        self.loop_thread = Thread(target=self.run_loop, daemon=True)
        self.loop_thread.start()
        self.enabled_checks = {
            "syntax": True,
            "misspelled": True,
            "placeholder_mismatch": True,
            "placeholder_order": True,
            "invalid_placeholder": True,
            "repeated_word": True,
            "drive_cycle": True,
            "success_criteria": True,
            "duplicate_scenario": True
        }

    def run_loop(self):
        """Run the asyncio event loop in a separate thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop_loop(self):
        """Stop the asyncio event loop and clean up."""
        self.loop.call_soon_threadsafe(self.loop.stop)
        while self.loop.is_running():
            time.sleep(0.1)
        self.loop.close()

    def load_config(self):
        config_file = "config.json"
        default_config = {
            "jira_url": "https://jira.devops.jlr-apps.com",
            "token_file": "auth_token.json",
            "batch_size": 10,
            "max_workers": 4,
            "proxies": {"http": "", "https": ""},
            "timeout": 5,
            "progress_update_interval": 0.5
        }
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    loaded_config = json.load(f)
                config = default_config.copy()
                config.update(loaded_config)
                logging.debug(f"Loaded configuration: {config}")
                return config
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Failed to load config file: {e}. Using default configuration.")
        return default_config

    def setup_gui(self):
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        try:
            self.root.iconbitmap(resource_path("icons/app_icon.ico"))
        except Exception as e:
            logging.warning(f"Failed to set main window icon: {e}")

        if self.app_icon:
            try:
                self.root.iconphoto(True, self.app_icon)
            except Exception as e:
                logging.warning(f"Failed to set taskbar icon: {e}")

        self.auth_frame = ctk.CTkFrame(self.root)
        self.auth_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.auth_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.online_switch = ctk.CTkSwitch(self.auth_frame, text="Online Mode", command=self.toggle_online_mode)
        self.online_switch.grid(row=0, column=4, padx=5, pady=5, sticky="e")

        self.auth_method_var = ctk.StringVar(value="pat")
        self.label_auth_method = ctk.CTkLabel(self.auth_frame, text="Authentication Method:")
        self.auth_method_dropdown = ctk.CTkOptionMenu(self.auth_frame, values=["PAT", "API Token"], variable=self.auth_method_var, command=self.update_auth_fields)
        self.label_pat = ctk.CTkLabel(self.auth_frame, text="Personal Access Token")
        self.entry_pat = ctk.CTkEntry(self.auth_frame, show="*")
        self.label_username = ctk.CTkLabel(self.auth_frame, text="Username")
        self.entry_username = ctk.CTkEntry(self.auth_frame)
        self.label_password = ctk.CTkLabel(self.auth_frame, text="API Token")
        self.entry_password = ctk.CTkEntry(self.auth_frame, show="*")
        try:
            save_icon_path = resource_path("icons/save_icon.png")
            if not os.path.exists(save_icon_path):
                raise FileNotFoundError(f"Icon file not found: {save_icon_path}")
            self.save_auth_button = ctk.CTkButton(
                self.auth_frame,
                text="Login",
                command=self.save_auth,
                image=ctk.CTkImage(light_image=Image.open(save_icon_path), size=(20, 20)),
                compound="left"
            )
        except Exception as e:
            logging.warning(f"Failed to load save_icon.png: {e}")
            self.save_auth_button = ctk.CTkButton(self.auth_frame, text="Login", command=self.save_auth)

        self.label_authenticated_user = ctk.CTkLabel(self.auth_frame, text="Authenticated User: Not logged in")

        self.spellcheck_frame = ctk.CTkFrame(self.root)
        self.spellcheck_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.spellcheck_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self.spellcheck_switch = ctk.CTkSwitch(self.spellcheck_frame, text="Enable Spellchecking", command=self.toggle_spellcheck)
        self.spellcheck_switch.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.spellcheck_language_var = ctk.StringVar(value="en_UK")
        self.label_spellcheck_language = ctk.CTkLabel(self.spellcheck_frame, text="Spellcheck Language:")
        self.spellcheck_language_dropdown = ctk.CTkOptionMenu(self.spellcheck_frame, values=["en_UK", "en_US"], variable=self.spellcheck_language_var, command=self.update_spellcheck_language)
        self.label_spellcheck_language.grid(row=0, column=1, padx=5, sticky="w")
        self.spellcheck_language_dropdown.grid(row=0, column=2, padx=5, sticky="ew")

        self.report_frame = ctk.CTkFrame(self.root)
        self.report_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.report_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.label_report_format = ctk.CTkLabel(self.report_frame, text="Report Format:")
        self.report_format_var = ctk.StringVar(value="text")
        self.report_format_dropdown = ctk.CTkOptionMenu(self.report_frame, values=["Text", "JSON"], variable=self.report_format_var)
        self.label_report_format.grid(row=0, column=0, padx=5, sticky="w")
        self.report_format_dropdown.grid(row=0, column=1, padx=5, sticky="ew")
        self.label_report_checks = ctk.CTkLabel(self.report_frame, text="Report Checks:")
        self.report_checks_button = ctk.CTkButton(self.report_frame, text="Select Checks", command=self.open_report_checks_dialog)
        self.label_report_checks.grid(row=0, column=2, padx=5, sticky="w")
        self.report_checks_button.grid(row=0, column=3, padx=5, sticky="ew")

        self.action_frame = ctk.CTkFrame(self.root)
        self.action_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        self.action_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self.label_action = ctk.CTkLabel(self.action_frame, text="Action:")
        self.label_action.grid(row=0, column=0, padx=5, sticky="w")
        self.action_var = ctk.StringVar(value="Run Checks on Files")
        self.action_dropdown = ctk.CTkOptionMenu(self.action_frame, values=["Run Checks on Files"], variable=self.action_var)
        self.action_dropdown.grid(row=0, column=1, padx=5, sticky="ew")
        self.label_key = ctk.CTkLabel(self.action_frame, text="Issue/Test Plan Key(s):")
        self.entry_key = ctk.CTkEntry(self.action_frame)
        try:
            execute_icon_path = resource_path("icons/execute_icon.png")
            if not os.path.exists(execute_icon_path):
                raise FileNotFoundError(f"Icon file not found: {execute_icon_path}")
            self.execute_button = ctk.CTkButton(
                self.action_frame,
                text="Execute",
                command=lambda: self.task_queue.put("execute_action"),
                image=ctk.CTkImage(light_image=Image.open(execute_icon_path), size=(20, 20)),
                compound="left"
            )
        except Exception as e:
            logging.warning(f"Failed to load execute_icon.png: {e}")
            self.execute_button = ctk.CTkButton(self.action_frame, text="Execute", command=lambda: self.task_queue.put("execute_action"))

        self.feature_frame = ctk.CTkFrame(self.root)
        self.feature_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
        self.feature_frame.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(self.feature_frame, text="Feature Type:").grid(row=0, column=0, padx=5, sticky="w")
        self.feature_type_var = ctk.StringVar(value="standard")
        feature_options = ["Standard", "Drive Cycle", "Success Criteria"]
        self.feature_dropdown = ctk.CTkOptionMenu(self.feature_frame, values=feature_options, variable=self.feature_type_var, command=self.update_feature_type)
        self.feature_dropdown.grid(row=0, column=1, padx=5, sticky="ew")

        self.status_indicator = ctk.CTkLabel(self.root, text="Idle", text_color="blue")
        self.status_indicator.grid(row=5, column=0, pady=5, sticky="ew")
        self.progress_bar = ctk.CTkProgressBar(self.root)
        self.progress_bar.grid(row=6, column=0, padx=10, pady=5, sticky="ew")
        self.download_progress_label = ctk.CTkLabel(self.root, text="")
        self.download_progress_label.grid(row=7, column=0, pady=5, sticky="ew")

        file_frame = ctk.CTkFrame(self.root)
        file_frame.grid(row=8, column=0, padx=10, pady=5, sticky="ew")
        file_frame.grid_columnconfigure((0, 1, 2), weight=1)
        try:
            select_files_icon_path = resource_path("icons/select_files_icon.png")
            if not os.path.exists(select_files_icon_path):
                raise FileNotFoundError(f"Icon file not found: {select_files_icon_path}")
            ctk.CTkButton(
                file_frame,
                text="Select Files",
                command=self.select_files,
                image=ctk.CTkImage(light_image=Image.open(select_files_icon_path), size=(20, 20)),
                compound="left"
            ).grid(row=0, column=0, padx=5, sticky="ew")
        except Exception as e:
            logging.warning(f"Failed to load select_files_icon.png: {e}")
            ctk.CTkButton(file_frame, text="Select Files", command=self.select_files).grid(row=0, column=0, padx=5, sticky="ew")

        try:
            select_folder_icon_path = resource_path("icons/select_folder_icon.png")
            if not os.path.exists(select_folder_icon_path):
                raise FileNotFoundError(f"Icon file not found: {select_folder_icon_path}")
            ctk.CTkButton(
                file_frame,
                text="Select Folder",
                command=self.select_folder,
                image=ctk.CTkImage(light_image=Image.open(select_folder_icon_path), size=(20, 20)),
                compound="left"
            ).grid(row=0, column=1, padx=5, sticky="ew")
        except Exception as e:
            logging.warning(f"Failed to load select_folder_icon.png: {e}")
            ctk.CTkButton(file_frame, text="Select Folder", command=self.select_folder).grid(row=0, column=1, padx=5, sticky="ew")

        try:
            load_dict_icon_path = resource_path("icons/load_dict_icon.png")
            if not os.path.exists(load_dict_icon_path):
                raise FileNotFoundError(f"Icon file not found: {load_dict_icon_path}")
            ctk.CTkButton(
                file_frame,
                text="Load Custom Dictionary",
                command=self.load_custom_dictionary,
                image=ctk.CTkImage(light_image=Image.open(load_dict_icon_path), size=(20, 20)),
                compound="left"
            ).grid(row=0, column=2, padx=5, sticky="ew")
        except Exception as e:
            logging.warning(f"Failed to load load_dict_icon.png: {e}")
            ctk.CTkButton(file_frame, text="Load Custom Dictionary", command=self.load_custom_dictionary).grid(row=0, column=2, padx=5, sticky="ew")

        self.listbox_files = scrolledtext.ScrolledText(self.root, height=10)
        self.listbox_files.grid(row=9, column=0, padx=10, pady=5, sticky="nsew")
        self.listbox_files.configure(bg="#2B2B2B", fg="#DCE4EE", insertbackground="white")

        try:
            run_checks_icon_path = resource_path("icons/run_checks_icon.png")
            if not os.path.exists(run_checks_icon_path):
                raise FileNotFoundError(f"Icon file not found: {run_checks_icon_path}")
            self.run_checks_button = ctk.CTkButton(
                self.root,
                text="Run Checks",
                command=lambda: self.task_queue.put("run_checks_offline"),
                image=ctk.CTkImage(light_image=Image.open(run_checks_icon_path), size=(20, 20)),
                compound="left"
            )
        except Exception as e:
            logging.warning(f"Failed to load run_checks_icon.png: {e}")
            self.run_checks_button = ctk.CTkButton(self.root, text="Run Checks", command=lambda: self.task_queue.put("run_checks_offline"))
        self.run_checks_button.grid(row=10, column=0, pady=10, sticky="ew")

        self.hide_online_elements()

    def hide_online_elements(self):
        """Hide online mode elements by default."""
        self.label_auth_method.grid_forget()
        self.auth_method_dropdown.grid_forget()
        self.label_pat.grid_forget()
        self.entry_pat.grid_forget()
        self.label_username.grid_forget()
        self.entry_username.grid_forget()
        self.label_password.grid_forget()
        self.entry_password.grid_forget()
        self.save_auth_button.grid_forget()
        self.label_authenticated_user.grid_forget()
        self.label_key.grid_forget()
        self.entry_key.grid_forget()
        self.execute_button.grid_forget()
        self.run_checks_button.configure(state="normal")
        self.update_action_dropdown()

    def show_online_elements(self):
        """Show online mode elements based on authentication method."""
        self.label_auth_method.grid(row=0, column=0, padx=5, sticky="w")
        self.auth_method_dropdown.grid(row=0, column=1, padx=5, sticky="ew")
        self.update_auth_fields(self.auth_method_var.get())
        self.save_auth_button.grid(row=0, column=3, padx=5, sticky="ew")
        self.label_authenticated_user.grid(row=1, column=0, columnspan=5, pady=5, sticky="ew")
        self.label_key.grid(row=0, column=2, padx=5, sticky="w")
        self.entry_key.grid(row=0, column=3, padx=5, sticky="ew")
        self.execute_button.grid(row=0, column=4, padx=5, sticky="ew")
        self.run_checks_button.configure(state="normal")
        self.update_action_dropdown()

    def update_auth_fields(self, auth_method):
        """Update authentication fields based on selected method."""
        if auth_method.lower() == "pat":
            self.label_pat.grid(row=2, column=0, padx=5, sticky="w")
            self.entry_pat.grid(row=2, column=1, columnspan=3, padx=5, sticky="ew")
            self.label_username.grid_forget()
            self.entry_username.grid_forget()
            self.label_password.grid_forget()
            self.entry_password.grid_forget()
        else:
            self.label_pat.grid_forget()
            self.entry_pat.grid_forget()
            self.label_username.grid(row=2, column=0, padx=5, sticky="w")
            self.entry_username.grid(row=2, column=1, padx=5, sticky="ew")
            self.label_password.grid(row=2, column=2, padx=5, sticky="w")
            self.entry_password.grid(row=2, column=3, padx=5, sticky="ew")

    def toggle_online_mode(self):
        """Toggle between online and offline modes."""
        self.online_mode = self.online_switch.get()
        if self.online_mode:
            self.show_online_elements()
            self.start_network_check()
        else:
            self.hide_online_elements()
            self.network_check_running = False
            self.status_indicator.configure(text="Idle", text_color="blue")

    def start_network_check(self):
        """Start periodic network status checks in online mode."""
        if not self.network_check_running:
            self.network_check_running = True
            self.executor.submit(self.network_check_loop)

    def network_check_loop(self):
        """Periodically check network status and update UI."""
        while self.network_check_running and self.online_mode:
            try:
                response = requests.get(self.config["jira_url"], timeout=self.config["timeout"], proxies=self.config["proxies"])
                if response.status_code == 200:
                    self.root.after(0, lambda: self.status_indicator.configure(text="Online", text_color="green"))
                else:
                    self.root.after(0, lambda: self.status_indicator.configure(text="Offline", text_color="red"))
            except requests.RequestException:
                self.root.after(0, lambda: self.status_indicator.configure(text="Offline", text_color="red"))
            time.sleep(5)

    def toggle_spellcheck(self):
        """Toggle spellchecking on or off."""
        self.spellcheck_enabled = self.spellcheck_switch.get()
        self.checker.spellcheck_enabled = self.spellcheck_enabled
        if self.spellcheck_enabled and not self.spellchecker:
            messagebox.showwarning("Warning", "Spellchecking unavailable. Install 'pyenchant' for British English spellcheck.")
            self.spellcheck_switch.deselect()
            self.spellcheck_enabled = False
            self.checker.spellcheck_enabled = False

    def update_spellcheck_language(self, language):
        """Update the spellcheck language."""
        self.spellcheck_language = language
        if self.spellcheck_enabled and SPELLCHECK_AVAILABLE:
            try:
                self.spellchecker = enchant.Dict(self.spellcheck_language)
                self.checker.spellchecker = self.spellchecker
                self.checker.spellcheck_language = self.spellcheck_language
            except enchant.errors.DictNotFoundError:
                messagebox.showerror("Error", f"Dictionary for language {self.spellcheck_language} not found.")
                self.spellcheck_language_var.set("en_UK")
                self.spellchecker = enchant.Dict("en_UK")
                self.checker.spellchecker = self.spellchecker
                self.checker.spellcheck_language = "en_UK"

    def open_report_checks_dialog(self):
        """Open a dialog to select which report checks to enable."""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Select Report Checks")
        dialog.minsize(300, 400)
        dialog.transient(self.root)
        dialog.grab_set()

        checks = [
            ("Syntax Errors", "syntax"),
            ("Misspelled Words", "misspelled"),
            ("Placeholder Mismatch", "placeholder_mismatch"),
            ("Placeholder Order", "placeholder_order"),
            ("Invalid Placeholder Syntax", "invalid_placeholder"),
            ("Repeated Words", "repeated_word"),
            ("Drive Cycle Format", "drive_cycle"),
            ("Success Criteria Format", "success_criteria"),
            ("Duplicate Scenarios", "duplicate_scenario")
        ]

        check_vars = {}
        for idx, (label, key) in enumerate(checks):
            var = ctk.BooleanVar(value=self.enabled_checks[key])
            check_vars[key] = var
            ctk.CTkCheckBox(dialog, text=label, variable=var).grid(row=idx, column=0, padx=10, pady=5, sticky="w")

        def save_checks():
            for key, var in check_vars.items():
                self.enabled_checks[key] = var.get()
            dialog.destroy()

        ctk.CTkButton(dialog, text="Save", command=save_checks).grid(row=len(checks), column=0, pady=10)

    def load_spell_cache(self):
        """Load the spellcheck cache from a file."""
        if os.path.exists(self.spell_cache_file):
            try:
                with open(self.spell_cache_file, "rb") as f:
                    self.spell_cache = pickle.load(f)
            except (pickle.PickleError, IOError) as e:
                logging.error(f"Failed to load spell cache: {e}")
                self.spell_cache = {}

    def save_spell_cache(self):
        """Save the spellcheck cache to a file."""
        try:
            with open(self.spell_cache_file, "wb") as f:
                pickle.dump(self.spell_cache, f)
        except IOError as e:
            logging.error(f"Failed to save spell cache: {e}")

    def load_custom_dictionary(self):
        """Load a custom dictionary file to add words to the spellchecker."""
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    words = f.read().splitlines()
                self.custom_words.update(word.strip().lower() for word in words if word.strip())
                messagebox.showinfo("Success", f"Loaded {len(words)} words into custom dictionary.")
            except Exception as e:
                logging.error(f"Failed to load custom dictionary: {e}")
                messagebox.showerror("Error", f"Failed to load custom dictionary: {str(e)}")

    def select_files(self):
        """Select multiple feature files to process."""
        files = filedialog.askopenfilenames(filetypes=[("Feature files", "*.feature")])
        if files:
            self.listbox_files.delete("1.0", "end")
            for file in files:
                self.listbox_files.insert("end", f"{file}\n")

    def select_folder(self):
        """Select a folder and load all feature files within it."""
        folder = filedialog.askdirectory()
        if folder:
            feature_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".feature")]
            self.listbox_files.delete("1.0", "end")
            for file in feature_files:
                self.listbox_files.insert("end", f"{file}\n")

    def select_download_location(self):
        """Prompt the user to select a directory for downloading files."""
        return filedialog.askdirectory()

    def update_feature_type(self, feature_type):
        """Update the feature type for validation."""
        self.feature_type = feature_type.lower().replace(" ", "_")
        self.checker.feature_type = self.feature_type

    def load_saved_pat(self):
        """Load saved PAT from the token file."""
        token_file = self.config["token_file"]
        if os.path.exists(token_file):
            try:
                with open(token_file, "r") as f:
                    data = json.load(f)
                self.pat = data.get("pat")
                self.username = data.get("username")
                if self.pat:
                    self.jira_client = JIRA(
                        server=self.config["jira_url"],
                        token_auth=self.pat,
                        options={"verify": True}
                    )
                    user = self.jira_client.myself()
                    self.label_authenticated_user.configure(text=f"Authenticated User: {user['displayName']}")
                    self.entry_pat.delete(0, "end")
                    self.entry_pat.insert(0, self.pat)
                    logging.info(f"Successfully loaded saved PAT and authenticated as {user['displayName']}")
                else:
                    self.label_authenticated_user.configure(text="Authenticated User: Not logged in")
            except (json.JSONDecodeError, IOError, JIRAError) as e:
                logging.error(f"Failed to load saved PAT: {e}")
                self.jira_client = None
                self.pat = None
                self.username = None
                self.label_authenticated_user.configure(text="Authenticated User: Not logged in")

    def save_auth(self):
        """Save authentication credentials and authenticate with Jira."""
        auth_method = self.auth_method_var.get().lower()
        if auth_method == "pat":
            self.pat = self.entry_pat.get()
            if not self.pat:
                messagebox.showerror("Error", "Please enter a Personal Access Token.")
                return
            try:
                self.jira_client = JIRA(
                    server=self.config["jira_url"],
                    token_auth=self.pat,
                    options={"verify": True}
                )
                user = self.jira_client.myself()
                self.username = user["displayName"]
                token_file = self.config["token_file"]
                try:
                    with open(token_file, "w") as f:
                        json.dump({"pat": self.pat, "username": self.username}, f)
                    logging.info(f"Saved PAT to {token_file}")
                except IOError as e:
                    logging.error(f"Failed to save PAT to {token_file}: {e}")
                    messagebox.showerror("Error", f"Failed to save PAT: {str(e)}")
                    return
                self.label_authenticated_user.configure(text=f"Authenticated User: {self.username}")
                messagebox.showinfo("Success", "Authentication successful! PAT saved for future use.")
            except JIRAError as e:
                logging.error(f"Authentication failed: {e}")
                messagebox.showerror("Error", f"Authentication failed: {str(e)}")
                self.jira_client = None
                self.pat = None
                self.username = None
                self.label_authenticated_user.configure(text="Authenticated User: Not logged in")
        else:
            self.username = self.entry_username.get()
            api_token = self.entry_password.get()
            if not self.username or not api_token:
                messagebox.showerror("Error", "Please enter both username and API token.")
                return
            try:
                self.jira_client = JIRA(
                    server=self.config["jira_url"],
                    basic_auth=(self.username, api_token),
                    options={"verify": True}
                )
                user = self.jira_client.myself()
                self.pat = None
                with open(self.config["token_file"], "w") as f:
                    json.dump({"username": self.username, "api_token": api_token}, f)
                self.label_authenticated_user.configure(text=f"Authenticated User: {self.username}")
                messagebox.showinfo("Success", "Authentication successful!")
            except JIRAError as e:
                logging.error(f"Authentication failed: {e}")
                messagebox.showerror("Error", f"Authentication failed: {str(e)}")
                self.jira_client = None
                self.username = None
                self.label_authenticated_user.configure(text="Authenticated User: Not logged in")

    def validate_issue_key(self, issue_key):
        """Validate the format of a Jira issue key."""
        pattern = re.compile(r"^[A-Z]+-\d+$")
        if not pattern.match(issue_key):
            raise ValueError(f"Invalid issue key format: {issue_key}. Expected format: PROJECT-123")

    async def fetch_issue(self, issue_key):
        """Fetch a Jira issue asynchronously."""
        return self.jira_client.issue(issue_key)

    def validate_gherkin_content(self, content):
        """Validate that the content contains Gherkin keywords."""
        if not any(content.strip().startswith(kw) for kw in ("Feature", "Scenario", "Given", "When", "Then")):
            raise ValueError("Content does not appear to be in Gherkin format (missing Feature, Scenario, Given, When, or Then).")

    def export_to_cucumber(self, issue_key):
        """Export a Jira issue to Gherkin format."""
        try:
            self.validate_issue_key(issue_key)
            future = asyncio.run_coroutine_threadsafe(self.fetch_issue(issue_key), self.loop)
            issue = future.result(timeout=30)

            # Prioritize customfield_10602 for Gherkin content, as per the log
            gherkin_content = getattr(issue.fields, 'customfield_10602', None)

            if not gherkin_content or not isinstance(gherkin_content, str):
                logging.warning(f"No Gherkin content found in customfield_10602 for issue {issue_key}")
                raise ValueError(f"No Gherkin content found in customfield_10602 for issue {issue_key}")

            # Validate that the content is in Gherkin format
            self.validate_gherkin_content(gherkin_content)

            # If the content doesn't start with "Feature", prepend a default Feature line
            if not gherkin_content.strip().startswith("Feature"):
                gherkin_content = f"Feature: Gherkin Content for {issue_key}\n  Scenario: Default Scenario\n" + gherkin_content

            logging.info(f"Successfully retrieved Gherkin content for issue {issue_key} from customfield_10602")
            return gherkin_content

        except JIRAError as e:
            if "You do not have the permission to see the specified issue" in str(e):
                error_msg = (
                    f"Permission denied: You do not have access to view issue {issue_key}. "
                    "Please contact your Jira administrator to grant access."
                )
                logging.error(error_msg)
                raise ValueError(error_msg)
            logging.error(f"Failed to fetch issue {issue_key} from Jira: {e}")
            raise ValueError(f"Failed to fetch issue {issue_key}: {str(e)}")
        except AttributeError as e:
            logging.error(f"Error accessing fields for issue {issue_key}: {e}")
            raise ValueError(f"Error accessing fields for issue {issue_key}: {str(e)}")
        except ValueError as e:
            logging.error(f"Failed to export test case {issue_key} to Cucumber: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error exporting test case {issue_key}: {e}")
            raise ValueError(f"Unexpected error: {str(e)}")

    def normalize_gherkin_content(self, content):
        """Normalize Gherkin content by ensuring consistent formatting."""
        lines = content.splitlines()
        normalized_lines = []
        indent_level = 0
        for line in lines:
            line = line.rstrip()
            if not line:
                normalized_lines.append("")
                continue
            stripped_line = line.lstrip()
            if stripped_line:
                if stripped_line.startswith("Feature"):
                    indent_level = 0
                elif stripped_line.startswith(("Scenario", "Scenario Outline", "Background")):
                    indent_level = 2
                elif stripped_line.startswith(("Given", "When", "Then", "And", "But")):
                    indent_level = 4
                elif stripped_line.startswith("Examples"):
                    indent_level = 4
                elif stripped_line.startswith("|"):
                    indent_level = 6
                normalized_lines.append(" " * indent_level + stripped_line)
        return "\n".join(normalized_lines)

    def download_feature_files(self, issue_keys):
        """Download feature files for multiple issues."""
        if not self.jira_client:
            logging.error("Jira client not initialized. Cannot download feature files.")
            self.root.after(0, lambda: messagebox.showerror("Error", "Not authenticated. Please save credentials first."))
            self.root.after(0, lambda: self.execute_button.configure(state="normal"))
            return [], None

        # Split issue keys (e.g., "PETM-123, PETM-456" -> ["PETM-123", "PETM-456"])
        issue_keys = [key.strip() for key in issue_keys.split(",") if key.strip()]
        if not issue_keys:
            self.root.after(0, lambda: messagebox.showerror("Error", "No issue keys provided."))
            self.root.after(0, lambda: self.execute_button.configure(state="normal"))
            return [], None

        download_dir_event = Event()
        download_dir_result = [None]

        def set_download_dir():
            result = self.select_download_location()
            download_dir_result[0] = result
            download_dir_event.set()

        self.root.after(0, set_download_dir)
        download_dir_event.wait()
        download_dir = download_dir_result[0]

        if not download_dir:
            logging.info("Download cancelled by user")
            self.root.after(0, lambda: messagebox.showinfo("Info", "Download cancelled by user"))
            self.root.after(0, lambda: self.execute_button.configure(state="normal"))
            return [], None

        logging.info(f"Attempting to download feature files for issues {issue_keys} to {download_dir}")
        self.root.after(0, lambda: self.status_indicator.configure(text="Downloading", text_color="orange"))

        feature_files = []
        total_issues = len(issue_keys)
        skipped_files = 0

        for idx, issue_key in enumerate(issue_keys):
            try:
                self.validate_issue_key(issue_key)
                gherkin_content = self.export_to_cucumber(issue_key)
                if not gherkin_content:
                    logging.warning(f"No Gherkin content generated for issue {issue_key}")
                    skipped_files += 1
                    continue

                gherkin_content = self.normalize_gherkin_content(gherkin_content)
                filename = os.path.join(download_dir, f"{issue_key}.feature")
                logging.debug(f"Writing Gherkin content to {filename}")

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(gherkin_content)
                logging.info(f"Successfully downloaded feature file: {filename}")

                if not os.path.exists(filename):
                    logging.error(f"Feature file {filename} was not created")
                    skipped_files += 1
                    continue

                feature_files.append(filename)

            except ValueError as e:
                logging.warning(f"Skipping issue {issue_key}: {e}")
                skipped_files += 1
            except Exception as e:
                logging.error(f"Unexpected error downloading feature file for issue {issue_key}: {e}")
                skipped_files += 1

            # Update progress
            progress = (idx + 1) / total_issues
            self.root.after(0, lambda p=progress: self.progress_bar.set(p))
            self.root.after(0, lambda: self.download_progress_label.configure(
                text=f"Downloaded {len(feature_files)} of {total_issues} files (skipped {skipped_files})"
            ))

        if not feature_files:
            self.root.after(0, lambda: messagebox.showwarning("Warning", f"No valid feature files downloaded for issues {', '.join(issue_keys)}"))
        else:
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Downloaded {len(feature_files)} feature files to {download_dir}"))

        self.root.after(0, lambda: self.status_indicator.configure(text="Idle", text_color="blue"))
        self.root.after(0, lambda: self.download_progress_label.configure(text=""))
        self.root.after(0, lambda: self.execute_button.configure(state="normal"))
        return feature_files, download_dir

    async def fetch_test_plan_tests(self, test_plan_key):
        """Fetch tests associated with a test plan using the Xray for Jira API."""
        if not self.pat:
            raise ValueError("Not authenticated. Please save credentials first.")

        try:
            # Construct the Xray API URL to fetch tests associated with the test plan
            xray_url = f"{self.config['jira_url']}/rest/raven/1.0/api/testplan/{test_plan_key}/test"
            headers = {
                "Authorization": f"Bearer {self.pat}",
                "Content-Type": "application/json"
            }

            logging.debug(f"Sending GET request: URL={xray_url}, Headers={headers}")
            async with aiohttp.ClientSession() as session:
                async with session.get(xray_url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logging.error(f"Failed to fetch tests for test plan {test_plan_key}: Status={response.status}, Response={error_text}")
                        raise ValueError(f"Failed to fetch tests for test plan {test_plan_key}: {error_text}")

                    tests_data = await response.json()
                    logging.debug(f"Received response: Status={response.status}, Response Text={tests_data}")

                    if not tests_data:
                        logging.warning(f"No tests found for test plan {test_plan_key}")
                        return []

                    # Extract test keys from the response
                    test_keys = [test["key"] for test in tests_data if test.get("key")]
                    tests = [{"key": key} for key in set(test_keys)]  # Remove duplicates
                    logging.info(f"Found {len(tests)} tests in test plan {test_plan_key}: {test_keys}")
                    return tests

        except aiohttp.ClientError as e:
            logging.error(f"Network error fetching tests for test plan {test_plan_key}: {e}")
            raise ValueError(f"Network error: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error fetching tests for test plan {test_plan_key}: {e}")
            raise ValueError(f"Unexpected error: {str(e)}")

    def get_test_plan_features(self, test_plan_key):
        """Fetch feature files from a test plan without blocking the main thread."""
        if not self.jira_client:
            self.root.after(0, lambda: messagebox.showerror("Error", "Not authenticated. Please save credentials first."))
            self.root.after(0, lambda: self.execute_button.configure(state="normal"))
            return []

        download_dir_event = Event()
        download_dir_result = [None]

        def set_download_dir():
            result = self.select_download_location()
            download_dir_result[0] = result
            download_dir_event.set()

        self.root.after(0, set_download_dir)
        download_dir_event.wait()
        download_dir = download_dir_result[0]

        if not download_dir:
            self.root.after(0, lambda: messagebox.showinfo("Info", "Download cancelled by user"))
            self.root.after(0, lambda: self.execute_button.configure(state="normal"))
            return []

        logging.info(f"Selected download location: {download_dir}")
        self.root.after(0, lambda: self.status_indicator.configure(text="Downloading", text_color="orange"))

        # Fetch the list of test cases associated with the test plan
        future = asyncio.run_coroutine_threadsafe(self.fetch_test_plan_tests(test_plan_key), self.loop)
        try:
            tests = future.result(timeout=30)
        except Exception as e:
            logging.error(f"Failed to fetch test plan {test_plan_key}: {e}")
            self.root.after(0, lambda err=str(e): messagebox.showerror("Error", f"Failed to fetch test plan {test_plan_key}: {err}"))
            self.root.after(0, lambda: self.status_indicator.configure(text="Error", text_color="red"))
            self.root.after(0, lambda: self.execute_button.configure(state="normal"))
            return []

        total_tests = len(tests)
        if total_tests == 0:
            self.root.after(0, lambda: messagebox.showwarning("Warning", f"No tests found in test plan {test_plan_key}"))
            self.root.after(0, lambda: self.status_indicator.configure(text="Idle", text_color="blue"))
            self.root.after(0, lambda: self.execute_button.configure(state="normal"))
            return []

        self.root.after(0, lambda: self.download_progress_label.configure(text=f"Found {total_tests} tests in test plan"))

        feature_files = []
        skipped_files = 0
        for idx, test in enumerate(tests):
            issue_key = test['key']
            try:
                # Fetch Gherkin content for the test case
                gherkin_content = self.export_to_cucumber(issue_key)
                if gherkin_content:
                    gherkin_content = self.normalize_gherkin_content(gherkin_content)
                    filename = os.path.join(download_dir, f"{issue_key}.feature")
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(gherkin_content)
                    feature_files.append(filename)
                    logging.info(f"Successfully downloaded feature file: {filename}")
            except ValueError as e:
                logging.warning(f"Skipping issue {issue_key} in test plan {test_plan_key}: {e}")
                skipped_files += 1
            except Exception as e:
                logging.error(f"Unexpected error downloading issue {issue_key}: {e}")
                skipped_files += 1

            # Update progress
            progress = (idx + 1) / total_tests
            self.root.after(0, lambda p=progress: self.progress_bar.set(p))
            self.root.after(0, lambda: self.download_progress_label.configure(
                text=f"Downloaded {len(feature_files)} of {total_tests} files (skipped {skipped_files})"
            ))

        if not feature_files:
            self.root.after(0, lambda: messagebox.showwarning("Warning", f"No valid .feature files found in test plan {test_plan_key}"))
        else:
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Downloaded {len(feature_files)} feature files to {download_dir}"))

        self.root.after(0, lambda: self.status_indicator.configure(text="Idle", text_color="blue"))
        self.root.after(0, lambda: self.download_progress_label.configure(text=""))
        self.root.after(0, lambda: self.execute_button.configure(state="normal"))
        return feature_files

    def run_checks(self, files, report_dir=None):
        """Run checks on the provided feature files and save reports in the specified directory."""
        if not files:
            self.root.after(0, lambda: messagebox.showwarning("Warning", "No files selected to check."))
            self.root.after(0, lambda: self.status_indicator.configure(text="Idle", text_color="blue"))
            return [], None

        self.root.after(0, lambda: self.status_indicator.configure(text="Checking", text_color="orange"))
        self.root.after(0, lambda: self.progress_bar.set(0))

        total_files = len(files)
        reports = []
        for idx, file in enumerate(files):
            report = TestReport(enabled_checks=self.enabled_checks)
            success = self.checker.process_file(file, report)
            if success:
                reports.append(report)
            progress = (idx + 1) / total_files
            with self.progress_lock:
                current_time = time.time()
                if current_time - self.last_progress_update >= self.config["progress_update_interval"]:
                    self.root.after(0, lambda p=progress: self.progress_bar.set(p))
                    self.last_progress_update = current_time

        self.root.after(0, lambda: self.progress_bar.set(1))
        self.root.after(0, lambda: self.status_indicator.configure(text="Idle", text_color="blue"))

        if not reports:
            self.root.after(0, lambda: messagebox.showwarning("Warning", "No valid feature files were processed."))
            return [], None

        report_format = self.report_format_var.get().lower()
        report_content = []
        total_errors = 0
        for report in reports:
            total_errors += report.get_total_errors()
            report_content.append(report.generate_report(format=report_format))

        # Save individual reports in the specified directory
        if report_dir:
            for idx, (report, content) in enumerate(zip(reports, report_content)):
                report_filename = os.path.join(report_dir, f"report_{os.path.basename(report.filename).replace('.feature', '')}.{report_format}")
                if report_format == "text":
                    with open(report_filename, "w", encoding="utf-8") as f:
                        f.write(content)
                else:
                    with open(report_filename, "w", encoding="utf-8") as f:
                        json.dump(content, f, indent=4)
                logging.info(f"Saved report to {report_filename}")

        # Generate a summary report
        summary_filename = os.path.join(report_dir if report_dir else ".", f"summary_report.{report_format}")
        if report_format == "text":
            summary_content = f"Summary Report\nTotal Files Processed: {len(reports)}\nTotal Errors Found: {total_errors}\n\n"
            summary_content += "\n\n".join(report_content)
            with open(summary_filename, "w", encoding="utf-8") as f:
                f.write(summary_content)
        else:
            summary_content = {
                "total_files": len(reports),
                "total_errors": total_errors,
                "reports": report_content
            }
            with open(summary_filename, "w", encoding="utf-8") as f:
                json.dump(summary_content, f, indent=4)

        self.root.after(0, lambda: messagebox.showinfo("Success", f"Summary report generated: {summary_filename}\nTotal errors found: {total_errors}"))

        return reports, summary_content

    def show_report_preview(self, reports, summary_content):
        """Show a preview of the bulk reports in a new window."""
        preview_window = ctk.CTkToplevel(self.root)
        preview_window.title("Report Preview")
        preview_window.minsize(600, 400)
        preview_window.transient(self.root)
        preview_window.grab_set()

        report_format = self.report_format_var.get().lower()
        text_area = scrolledtext.ScrolledText(preview_window, height=20, width=80)
        text_area.pack(padx=10, pady=10, fill="both", expand=True)

        if report_format == "text":
            text_area.insert("end", summary_content)
        else:
            text_area.insert("end", json.dumps(summary_content, indent=4))

        text_area.configure(state="disabled")

        ctk.CTkButton(preview_window, text="Close", command=preview_window.destroy).pack(pady=10)

    def run_checks_on_feature_files(self, issue_keys):
        """Download feature files for multiple issues and run checks on them."""
        try:
            self.root.after(0, lambda: self.status_indicator.configure(text="Downloading", text_color="orange"))
            feature_files, download_dir = self.download_feature_files(issue_keys)
            if not feature_files:
                self.root.after(0, lambda: self.status_indicator.configure(text="Idle", text_color="blue"))
                return

            self.root.after(0, lambda: self.listbox_files.delete("1.0", "end"))
            for file in feature_files:
                self.root.after(0, lambda f=file: self.listbox_files.insert("end", f"{f}\n"))

            reports, summary_content = self.run_checks(feature_files, report_dir=download_dir)
            if reports and summary_content:
                self.show_report_preview(reports, summary_content)

        except Exception as e:
            logging.error(f"Error running checks on feature files for issues {issue_keys}: {e}")
            self.root.after(0, lambda err=str(e): messagebox.showerror("Error", f"Error processing feature files: {err}"))
            self.root.after(0, lambda: self.status_indicator.configure(text="Idle", text_color="blue"))
        finally:
            self.root.after(0, lambda: self.execute_button.configure(state="normal"))

    def run_checks_on_test_plan(self, test_plan_key):
        """Run checks on all feature files associated with a test plan."""
        try:
            self.root.after(0, lambda: self.status_indicator.configure(text="Fetching Test Plan", text_color="orange"))
            feature_files = self.get_test_plan_features(test_plan_key)
            if not feature_files:
                self.root.after(0, lambda: self.status_indicator.configure(text="Idle", text_color="blue"))
                return

            download_dir = os.path.dirname(feature_files[0])  # Get the download directory from the first file
            self.root.after(0, lambda: self.listbox_files.delete("1.0", "end"))
            for file in feature_files:
                self.root.after(0, lambda f=file: self.listbox_files.insert("end", f"{f}\n"))

            reports, summary_content = self.run_checks(feature_files, report_dir=download_dir)
            if reports and summary_content:
                self.show_report_preview(reports, summary_content)

        except Exception as e:
            logging.error(f"Error running checks on test plan {test_plan_key}: {e}")
            self.root.after(0, lambda err=str(e): messagebox.showerror("Error", f"Error processing test plan: {err}"))
            self.root.after(0, lambda: self.status_indicator.configure(text="Idle", text_color="blue"))
        finally:
            self.root.after(0, lambda: self.execute_button.configure(state="normal"))

    def update_action_dropdown(self):
        """Update the action dropdown options based on the mode."""
        if self.online_mode:
            self.action_dropdown.configure(values=[
                "Download Feature Files",
                "Download Test Plan",
                "Run Checks on Feature Files",
                "Run Checks on Test Plan",
                "Run Checks on Files"
            ])
            self.action_var.set("Download Feature Files")
        else:
            self.action_dropdown.configure(values=["Run Checks on Files"])
            self.action_var.set("Run Checks on Files")

    def execute_action(self):
        """Execute the selected action (download or run checks)."""
        action = self.action_var.get()
        keys = self.entry_key.get().strip()
        self.execute_button.configure(state="disabled")

        # Map display names to internal actions
        action_map = {
            "Download Feature Files": "download_feature_files",
            "Download Test Plan": "download_test_plan",
            "Run Checks on Feature Files": "run_checks_on_feature_files",
            "Run Checks on Test Plan": "run_checks_on_test_plan",
            "Run Checks on Files": "run_checks_files"
        }
        internal_action = action_map.get(action)

        if not internal_action:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Invalid action selected: {action}"))
            self.root.after(0, lambda: self.execute_button.configure(state="normal"))
            return

        if not keys and internal_action in ["download_feature_files", "download_test_plan", "run_checks_on_feature_files", "run_checks_on_test_plan"]:
            self.root.after(0, lambda: messagebox.showerror("Error", "Please enter issue or test plan key(s)."))
            self.root.after(0, lambda: self.execute_button.configure(state="normal"))
            return

        if internal_action == "download_feature_files":
            self.executor.submit(self.download_feature_files, keys)
        elif internal_action == "download_test_plan":
            self.executor.submit(self.get_test_plan_features, keys)
        elif internal_action == "run_checks_on_feature_files":
            self.executor.submit(self.run_checks_on_feature_files, keys)
        elif internal_action == "run_checks_on_test_plan":
            self.executor.submit(self.run_checks_on_test_plan, keys)
        elif internal_action == "run_checks_files":
            files = self.listbox_files.get("1.0", "end").strip().splitlines()
            if not files or not files[0]:
                self.root.after(0, lambda: messagebox.showwarning("Warning", "No files selected to check."))
                self.root.after(0, lambda: self.execute_button.configure(state="normal"))
                return
            self.executor.submit(self.run_checks, files)

    def process_queue(self):
        """Process tasks from the queue in the main thread."""
        try:
            while True:
                task = self.task_queue.get_nowait()
                if task == "run_checks_offline":
                    files = self.listbox_files.get("1.0", "end").strip().splitlines()
                    if not files or not files[0]:
                        messagebox.showwarning("Warning", "No files selected to check.")
                        continue
                    self.executor.submit(self.run_checks, files)
                elif task == "execute_action":
                    self.execute_action()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def on_closing(self):
        """Handle application closing."""
        self.save_spell_cache()
        self.network_check_running = False
        self.executor.shutdown(wait=True)
        self.stop_loop()
        self.root.destroy()

if __name__ == "__main__":
    app = GherkinCheckerApp()
    app.process_queue()
    app.root.mainloop()