import sys
import os
import sys
if sys.platform == 'win32':
    import comtypes.client

class WindowsFirewallChecker:
    """
    Provides static methods to check Windows Firewall rules for the current executable and inform the user what to do.
    """

    @staticmethod
    def check_firewall_rule(verbose: bool = False):
        # Returns:
        #   has_rule: True if an enabled allow rule exists for the current profile
        #   current_profile: The detected network profile (or 'private' as fallback)
        #   rule_profiles: List of profiles for which an enabled allow rule exists
        #   enabled_profiles: Set of profiles with enabled allow rules
        #   disabled_profiles: Set of profiles with disabled rules
        #   has_block: True if an enabled block rule exists for the current profile
        def _get_executable_path() -> str:
            # Nuitka: module-level __compiled__ is True
            if getattr(sys, 'frozen', False) or getattr(sys.modules[__name__], '__compiled__', False):
                return os.path.abspath(sys.argv[0])
            else:
                return os.path.abspath(sys.executable)
        def _get_current_network_profile(verbose: bool = False) -> str:
            # Returns 'private' as a fallback for current network profile
            try:
                if verbose:
                    print("[FirewallChecker] Using fallback: returning 'private' as current network profile.")
                return 'private'
            except Exception as e:
                if verbose:
                    print(f"[FirewallChecker] Could not determine current network profile: {e}")
                return None
        exe_path = _get_executable_path()
        if verbose:
            print(f"[FirewallChecker] Checking firewall rule for application: {exe_path}")
        try:
            comtypes.CoInitialize()
            policy = comtypes.client.CreateObject('HNetCfg.FwPolicy2')
            rules = policy.Rules
            exe_path = exe_path.lower()
            enabled_profiles = set()  # Profiles with enabled allow rules
            disabled_profiles = set() # Profiles with disabled rules
            block_profiles = set()    # Profiles with enabled block rules
            for rule in rules:
                try:
                    if rule.ApplicationName and rule.ApplicationName.lower() == exe_path:
                        if verbose:
                            # Action: 0 = block, 1 = allow
                            raw_action = rule.Action
                            if raw_action == 0:
                                action_str = 'block'
                            elif raw_action == 1:
                                action_str = 'allow'
                            else:
                                action_str = f'unknown ({raw_action})'
                            print(f"[FirewallChecker] Found rule: {rule.Name}, Enabled: {rule.Enabled}, Profiles: {rule.Profiles}, Action: {action_str} (raw: {raw_action}), Executable: {rule.ApplicationName}")
                        for prof, mask in [('domain', 1), ('private', 2), ('public', 4)]:
                            if rule.Profiles & mask:
                                if rule.Enabled:
                                    if rule.Action == 1:
                                        enabled_profiles.add(prof)
                                    elif rule.Action == 0:
                                        block_profiles.add(prof)
                                else:
                                    disabled_profiles.add(prof)
                                    if verbose:
                                        print(f"[FirewallChecker] Rule '{rule.Name}' is DISABLED (Enabled: False) for profile: {prof}")
                except Exception as e:
                    if verbose:
                        print(f"[FirewallChecker] Exception while checking rule: {e}")
                    continue
            current_profile = _get_current_network_profile(verbose=verbose)
            has_rule = current_profile in enabled_profiles if current_profile else False
            has_block = current_profile in block_profiles if current_profile else False
            if verbose:
                print(f"[FirewallChecker] has_rule: {has_rule}, has_block: {has_block}, current_profile: {current_profile}, enabled_profiles: {enabled_profiles}, block_profiles: {block_profiles}, disabled_profiles: {disabled_profiles}")
                if disabled_profiles:
                    print(f"[FirewallChecker] Disabled rules for profiles: {disabled_profiles}")
            return has_rule, current_profile, list(enabled_profiles), enabled_profiles, disabled_profiles, has_block
        except Exception as e:
            if verbose:
                print(f"[FirewallChecker] COM exception: {e}")
            return False, None, [], set(), set(), False
