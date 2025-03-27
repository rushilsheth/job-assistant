#!/usr/bin/env python3
"""
State management module for JobTracker application.
Maintains the state of job applications across sessions.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import threading

logger = logging.getLogger("job-tracker.state")

class StateManager:
    """Manages application state for job search tracking."""
    
    def __init__(self, state_file: str = None):
        """
        Initialize the state manager.
        
        Args:
            state_file: Path to the state file (default: ~/.job-tracker/state.json)
        """
        # Use default path if not provided
        if not state_file:
            home_dir = os.path.expanduser("~")
            state_dir = os.path.join(home_dir, ".job-tracker")
            if not os.path.exists(state_dir):
                os.makedirs(state_dir)
            self.state_file = os.path.join(state_dir, "state.json")
        else:
            self.state_file = state_file
        
        # Initialize state
        self.state = {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "companies": {},
            "stats": {
                "applications_sent": 0,
                "interviews_scheduled": 0,
                "offers_received": 0,
                "rejections": 0
            },
            "settings": {}
        }
        
        # Thread lock for thread safety
        self.lock = threading.Lock()
        
        # Load existing state if it exists
        self._load_state()
        
        logger.info(f"State manager initialized with state file: {self.state_file}")
    
    def _load_state(self):
        """Load state from file if it exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    loaded_state = json.load(f)
                    # Update our state with loaded state
                    self.state.update(loaded_state)
                logger.info(f"Loaded state from {self.state_file}")
            except Exception as e:
                logger.error(f"Error loading state from {self.state_file}: {e}")
                # Create backup of corrupted state file
                if os.path.exists(self.state_file):
                    backup_file = f"{self.state_file}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    try:
                        with open(self.state_file, 'r') as src, open(backup_file, 'w') as dst:
                            dst.write(src.read())
                        logger.info(f"Created backup of corrupted state file: {backup_file}")
                    except Exception as backup_err:
                        logger.error(f"Failed to backup corrupted state file: {backup_err}")
    
    def _save_state(self):
        """Save current state to file."""
        with self.lock:
            # Update last updated timestamp
            self.state["last_updated"] = datetime.now().isoformat()
            
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
                
                # Write to temp file first to avoid corruption on crash
                temp_file = f"{self.state_file}.tmp"
                with open(temp_file, 'w') as f:
                    json.dump(self.state, f, indent=2)
                
                # Replace the actual file with the temp file
                os.replace(temp_file, self.state_file)
                
                logger.info(f"Saved state to {self.state_file}")
            except Exception as e:
                logger.error(f"Error saving state to {self.state_file}: {e}")
    
    def get_company_state(self, company_name: str) -> Dict[str, Any]:
        """
        Get state information for a specific company.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Dict with company state or empty dict if not found
        """
        with self.lock:
            return self.state["companies"].get(company_name, {})
    
    def update_company_state(self, company_name: str, updates: Dict[str, Any]):
        """
        Update state for a specific company.
        
        Args:
            company_name: Name of the company
            updates: Dictionary of state updates
        """
        with self.lock:
            # Create company entry if it doesn't exist
            if company_name not in self.state["companies"]:
                self.state["companies"][company_name] = {
                    "created_at": datetime.now().isoformat(),
                    "status": "Not Applied",
                    "interactions": []
                }
            
            # Update company state
            company_state = self.state["companies"][company_name]
            company_state.update(updates)
            
            # Add to interactions if it's a new interaction type
            if "last_interaction" in updates and "last_interaction_date" in updates:
                interaction = {
                    "type": updates["last_interaction"],
                    "date": updates["last_interaction_date"]
                }
                
                # Add additional details if available
                for key in ["details", "notes"]:
                    if key in updates:
                        interaction[key] = updates[key]
                
                # Add to interactions list
                if "interactions" not in company_state:
                    company_state["interactions"] = []
                
                company_state["interactions"].append(interaction)
            
            # Update application status if needed
            if "status" in updates:
                old_status = company_state.get("status")
                new_status = updates["status"]
                
                # Update application stats based on status changes
                if old_status != new_status:
                    if new_status == "Applied" and old_status in [None, "Not Applied"]:
                        self.state["stats"]["applications_sent"] += 1
                    elif new_status == "Interview" and old_status != "Interview":
                        self.state["stats"]["interviews_scheduled"] += 1
                    elif new_status == "Offer" and old_status != "Offer":
                        self.state["stats"]["offers_received"] += 1
                    elif new_status == "Rejected" and old_status != "Rejected":
                        self.state["stats"]["rejections"] += 1
            
            # Save changes to disk
            self._save_state()
    
    def get_all_companies(self) -> Dict[str, Dict[str, Any]]:
        """
        Get state information for all companies.
        
        Returns:
            Dict mapping company names to their state information
        """
        with self.lock:
            return self.state["companies"].copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get application statistics.
        
        Returns:
            Dict with application statistics
        """
        with self.lock:
            return self.state["stats"].copy()
    
    def update_stats(self, updates: Dict[str, Any]):
        """
        Update application statistics.
        
        Args:
            updates: Dictionary of stat updates
        """
        with self.lock:
            self.state["stats"].update(updates)
            self._save_state()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.
        
        Args:
            key: Setting key
            default: Default value if setting not found
            
        Returns:
            Setting value or default
        """
        with self.lock:
            return self.state["settings"].get(key, default)
    
    def update_setting(self, key: str, value: Any):
        """
        Update a setting value.
        
        Args:
            key: Setting key
            value: Setting value
        """
        with self.lock:
            self.state["settings"][key] = value
            self._save_state()
    
    def clear_state(self):
        """Clear all state data."""
        with self.lock:
            self.state = {
                "version": self.state.get("version", "1.0"),
                "last_updated": datetime.now().isoformat(),
                "companies": {},
                "stats": {
                    "applications_sent": 0,
                    "interviews_scheduled": 0,
                    "offers_received": 0,
                    "rejections": 0
                },
                "settings": {}
            }
            self._save_state()