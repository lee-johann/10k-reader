#!/usr/bin/env python3
"""
Table Validation Module
Performs validation checks on extracted financial statements and returns checklist status.
"""

import pandas as pd
import re
from typing import Dict, List, Any, Optional, Tuple
import json
import sys


class FinancialStatementValidator:
    """
    Validates financial statements and performs checklist checks.
    """
    
    def __init__(self, statements_data: List[Dict[str, Any]]):
        """
        Initialize with extracted statements data.
        
        Args:
            statements_data: List of statement dictionaries from the extraction
        """
        self.statements = statements_data
        self.checklist_results = {}
        
    def normalize_number(self, value: str) -> float:
        """
        Convert string number to float, handling various formats.
        
        Args:
            value: String representation of number
            
        Returns:
            float: Normalized number value
        """
        if not value or value == '' or value == 'nan':
            return 0.0
            
        # Remove common formatting
        clean_value = str(value).replace('$', '').replace(',', '').replace('(', '').replace(')', '')
        
        # Handle negative numbers in parentheses
        if '(' in str(value) and ')' in str(value):
            clean_value = '-' + clean_value.replace('(', '').replace(')', '')
        
        try:
            return float(clean_value)
        except ValueError:
            return 0.0
    
    def get_statement_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific statement by name.
        
        Args:
            name: Statement name to find
            
        Returns:
            Dict containing statement data or None if not found
        """
        for statement in self.statements:
            if statement['name'].upper() in name.upper() or name.upper() in statement['name'].upper():
                return statement
        return None
    
    def find_row_by_description(self, statement: Dict[str, Any], description_keywords: List[str]) -> Optional[Dict[str, str]]:
        """
        Find a row in the statement by description keywords.
        
        Args:
            statement: Statement data
            description_keywords: Keywords to search for in description
            
        Returns:
            Row data if found, None otherwise
        """
        for row in statement['tableData']:
            desc = row.get('Description', '').lower()
            if any(keyword.lower() in desc for keyword in description_keywords):
                return row
        return None
    
    def get_value_columns(self, statement: Dict[str, Any]) -> List[str]:
        """
        Get the value columns (excluding Description) from a statement.
        
        Args:
            statement: Statement data
            
        Returns:
            List of value column names
        """
        return [col for col in statement['headers'] if col != 'Description']
    
    def calculate_total_assets(self, balance_sheet: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate total assets by summing rows until hitting "Total assets".
        
        Args:
            balance_sheet: Balance sheet statement data
            
        Returns:
            Dict with calculated and reported totals
        """
        value_cols = self.get_value_columns(balance_sheet)
        calculated_total = 0.0
        reported_total = 0.0
        found_total_assets = False
        summed_rows = []
        
        # Find the "Total assets" row and get its reported value
        for row in balance_sheet['tableData']:
            desc = row.get('Description', '').lower()
            if 'total assets' in desc:
                for col in value_cols:
                    reported_total += self.normalize_number(row.get(col, 0))
                found_total_assets = True
                break
        
        if not found_total_assets:
            return {
                'calculated': 0.0,
                'reported': 0.0,
                'difference': 0.0,
                'matches': False
            }
        
        # Sum all rows above "Total assets" that don't contain "total" in description
        for row in balance_sheet['tableData']:
            desc = row.get('Description', '').lower()
            
            # Stop when we hit "Total assets"
            if 'total assets' in desc:
                break
            
            # Skip rows that contain "total" (these are subtotals)
            if 'total' in desc:
                continue
            
            # Skip empty descriptions or section headers
            if not desc or desc in ['assets', 'current assets:', 'liabilities and stockholders\' equity']:
                continue
            
            # Sum the values for this row
            row_total = 0.0
            for col in value_cols:
                row_total += self.normalize_number(row.get(col, 0))
            
            if row_total > 0:
                calculated_total += row_total
                summed_rows.append(f"{row.get('Description', '')}: {row_total:,.0f}")
        
        print(f"ASSETS CALCULATION:", file=sys.stderr)
        print(f"  Summed rows: {summed_rows}", file=sys.stderr)
        print(f"  Calculated total: {calculated_total:,.0f}", file=sys.stderr)
        print(f"  Reported total: {reported_total:,.0f}", file=sys.stderr)
        print(f"  Difference: {abs(calculated_total - reported_total):,.0f}", file=sys.stderr)
        
        return {
            'calculated': calculated_total,
            'reported': reported_total,
            'difference': abs(calculated_total - reported_total),
            'matches': abs(calculated_total - reported_total) < 1000  # Allow small rounding differences
        }
    
    def calculate_total_liabilities_equity(self, balance_sheet: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate total liabilities and equity by summing rows until hitting the final total.
        
        Args:
            balance_sheet: Balance sheet statement data
            
        Returns:
            Dict with calculated and reported totals
        """
        value_cols = self.get_value_columns(balance_sheet)
        calculated_total = 0.0
        reported_total = 0.0
        found_final_total = False
        in_liabilities_section = False
        summed_rows = []
        
        # Find the final total row (usually "Total liabilities and stockholders' equity")
        final_total_keywords = ['total liabilities and stockholders', 'total liabilities and equity']
        for row in balance_sheet['tableData']:
            desc = row.get('Description', '').lower()
            if any(keyword in desc for keyword in final_total_keywords):
                for col in value_cols:
                    reported_total += self.normalize_number(row.get(col, 0))
                found_final_total = True
                break
        
        if not found_final_total:
            return {
                'calculated': 0.0,
                'reported': 0.0,
                'difference': 0.0,
                'matches': False
            }
        
        # Sum all rows in the liabilities and equity section that don't contain "total" in description
        for row in balance_sheet['tableData']:
            desc = row.get('Description', '').lower()
            
            # Start summing when we enter the liabilities section
            if 'liabilities and stockholders' in desc or 'liabilities and equity' in desc:
                in_liabilities_section = True
                continue
            
            # Stop when we hit the final total
            if any(keyword in desc for keyword in final_total_keywords):
                break
            
            # Only sum if we're in the liabilities section
            if not in_liabilities_section:
                continue
            
            # Skip rows that contain "total" (these are subtotals)
            if 'total' in desc:
                continue
            
            # Skip empty descriptions or section headers
            if not desc or desc in ['current liabilities:', 'stockholders\' equity:']:
                continue
            
            # Skip the "Commitments and Contingencies" row as it's not a financial item
            if 'commitments and contingencies' in desc:
                continue
            
            # Sum the values for this row
            row_total = 0.0
            for col in value_cols:
                row_total += self.normalize_number(row.get(col, 0))
            
            # Include all rows with values (including negative ones)
            if row_total != 0:  # Changed from > 0 to != 0 to include negative values
                calculated_total += row_total
                summed_rows.append(f"{row.get('Description', '')}: {row_total:,.0f}")
        
        print(f"LIABILITIES & EQUITY CALCULATION:", file=sys.stderr)
        print(f"  Summed rows: {summed_rows}", file=sys.stderr)
        print(f"  Calculated total: {calculated_total:,.0f}", file=sys.stderr)
        print(f"  Reported total: {reported_total:,.0f}", file=sys.stderr)
        print(f"  Difference: {abs(calculated_total - reported_total):,.0f}", file=sys.stderr)
        
        return {
            'calculated': calculated_total,
            'reported': reported_total,
            'difference': abs(calculated_total - reported_total),
            'matches': abs(calculated_total - reported_total) < 1000  # Allow small rounding differences
        }
    
    def validate_balance_sheet_checks(self) -> Dict[str, bool]:
        """
        Perform balance sheet validation checks.
        
        Returns:
            Dict with check results
        """
        balance_sheet = self.get_statement_by_name('BALANCE')
        if not balance_sheet:
            return {f'balance_sheet_{i}': False for i in range(1, 10)}
        
        value_cols = self.get_value_columns(balance_sheet)
        results = {}
        
        # Check 1: Assets = Liabilities + Stockholders' Equity
        total_assets = self.calculate_total_assets(balance_sheet)
        total_liab_equity = self.calculate_total_liabilities_equity(balance_sheet)
        results['balance_sheet_1'] = abs(total_assets['reported'] - total_liab_equity['reported']) < 1000
        
        # Check 2: Current assets > Current liabilities (working capital positive)
        current_assets_row = self.find_row_by_description(balance_sheet, ['Total current assets'])
        current_liab_row = self.find_row_by_description(balance_sheet, ['Total current liabilities'])
        
        if current_assets_row and current_liab_row:
            current_assets = sum(self.normalize_number(current_assets_row.get(col, 0)) for col in value_cols)
            current_liab = sum(self.normalize_number(current_liab_row.get(col, 0)) for col in value_cols)
            results['balance_sheet_2'] = current_assets > current_liab
        else:
            results['balance_sheet_2'] = False
        
        # Check 3: Cash and cash equivalents reasonable level
        cash_row = self.find_row_by_description(balance_sheet, ['Cash and cash equivalents'])
        if cash_row and total_assets['reported'] > 0:
            cash = sum(self.normalize_number(cash_row.get(col, 0)) for col in value_cols)
            cash_ratio = cash / total_assets['reported']
            results['balance_sheet_3'] = 0.05 <= cash_ratio <= 0.3  # 5-30% is reasonable
        else:
            results['balance_sheet_3'] = False
        
        # Check 4: Accounts receivable aging reasonable (simplified check)
        ar_row = self.find_row_by_description(balance_sheet, ['Accounts receivable'])
        if ar_row and total_assets['reported'] > 0:
            ar = sum(self.normalize_number(ar_row.get(col, 0)) for col in value_cols)
            ar_ratio = ar / total_assets['reported']
            results['balance_sheet_4'] = ar_ratio <= 0.2  # AR should not exceed 20% of assets
        else:
            results['balance_sheet_4'] = False
        
        # Check 5: Inventory levels appropriate (if inventory exists)
        inventory_row = self.find_row_by_description(balance_sheet, ['Inventory'])
        if inventory_row and total_assets['reported'] > 0:
            inventory = sum(self.normalize_number(inventory_row.get(col, 0)) for col in value_cols)
            inventory_ratio = inventory / total_assets['reported']
            results['balance_sheet_5'] = inventory_ratio <= 0.3  # Inventory should not exceed 30% of assets
        else:
            results['balance_sheet_5'] = True  # No inventory is fine for many companies
        
        # Check 6: Property, plant & equipment properly valued
        ppe_row = self.find_row_by_description(balance_sheet, ['Property and equipment'])
        if ppe_row and total_assets['reported'] > 0:
            ppe = sum(self.normalize_number(ppe_row.get(col, 0)) for col in value_cols)
            ppe_ratio = ppe / total_assets['reported']
            results['balance_sheet_6'] = ppe_ratio <= 0.6  # PPE should not exceed 60% of assets
        else:
            results['balance_sheet_6'] = True  # No PPE is fine for service companies
        
        # Check 7: Goodwill and intangibles reasonable
        goodwill_row = self.find_row_by_description(balance_sheet, ['Goodwill'])
        if goodwill_row and total_assets['reported'] > 0:
            goodwill = sum(self.normalize_number(goodwill_row.get(col, 0)) for col in value_cols)
            goodwill_ratio = goodwill / total_assets['reported']
            results['balance_sheet_7'] = goodwill_ratio <= 0.4  # Goodwill should not exceed 40% of assets
        else:
            results['balance_sheet_7'] = True  # No goodwill is fine
        
        # Check 8: Debt levels manageable
        debt_keywords = ['Long-term debt', 'Total liabilities']
        total_debt = 0
        for keyword in debt_keywords:
            debt_row = self.find_row_by_description(balance_sheet, [keyword])
            if debt_row:
                total_debt += sum(self.normalize_number(debt_row.get(col, 0)) for col in value_cols)
        
        if total_debt > 0 and total_assets['reported'] > 0:
            debt_ratio = total_debt / total_assets['reported']
            results['balance_sheet_8'] = debt_ratio <= 0.7  # Debt should not exceed 70% of assets
        else:
            results['balance_sheet_8'] = True  # No debt is good
        
        # Check 9: Retained earnings consistent with history (simplified)
        re_row = self.find_row_by_description(balance_sheet, ['Retained earnings'])
        if re_row:
            re_value = sum(self.normalize_number(re_row.get(col, 0)) for col in value_cols)
            results['balance_sheet_9'] = re_value >= 0  # Retained earnings should be positive
        else:
            results['balance_sheet_9'] = False
        
        return results
    
    def validate_income_statement_checks(self) -> Dict[str, bool]:
        """
        Perform income statement validation checks.
        
        Returns:
            Dict with check results
        """
        income_statement = self.get_statement_by_name('INCOME')
        if not income_statement:
            return {f'income_statement_{i}': False for i in range(1, 9)}
        
        value_cols = self.get_value_columns(income_statement)
        results = {}
        
        # Check 1: Revenue recognition appropriate (simplified - just check if revenue exists)
        revenue_row = self.find_row_by_description(income_statement, ['Revenues', 'Revenue'])
        results['income_statement_1'] = revenue_row is not None and any(
            self.normalize_number(revenue_row.get(col, 0)) > 0 for col in value_cols
        )
        
        # Check 2: Gross margin consistent with industry (simplified)
        revenue_row = self.find_row_by_description(income_statement, ['Revenues', 'Revenue'])
        cost_row = self.find_row_by_description(income_statement, ['Cost of revenues', 'Cost of sales'])
        
        if revenue_row and cost_row:
            revenue = sum(self.normalize_number(revenue_row.get(col, 0)) for col in value_cols)
            cost = sum(self.normalize_number(cost_row.get(col, 0)) for col in value_cols)
            if revenue > 0:
                gross_margin = (revenue - cost) / revenue
                results['income_statement_2'] = 0.1 <= gross_margin <= 0.9  # 10-90% is reasonable
            else:
                results['income_statement_2'] = False
        else:
            results['income_statement_2'] = False
        
        # Check 3: Operating expenses reasonable
        op_expense_keywords = ['Research and development', 'Sales and marketing', 'General and administrative']
        total_op_expenses = 0
        for keyword in op_expense_keywords:
            expense_row = self.find_row_by_description(income_statement, [keyword])
            if expense_row:
                total_op_expenses += sum(self.normalize_number(expense_row.get(col, 0)) for col in value_cols)
        
        revenue_row = self.find_row_by_description(income_statement, ['Revenues', 'Revenue'])
        if revenue_row and total_op_expenses > 0:
            revenue = sum(self.normalize_number(revenue_row.get(col, 0)) for col in value_cols)
            if revenue > 0:
                op_expense_ratio = total_op_expenses / revenue
                results['income_statement_3'] = op_expense_ratio <= 0.8  # Op expenses should not exceed 80% of revenue
            else:
                results['income_statement_3'] = False
        else:
            results['income_statement_3'] = True  # No operating expenses is unusual but possible
        
        # Check 4: EBITDA margins stable (simplified - check operating income)
        op_income_row = self.find_row_by_description(income_statement, ['Income from operations', 'Operating income'])
        revenue_row = self.find_row_by_description(income_statement, ['Revenues', 'Revenue'])
        
        if op_income_row and revenue_row:
            op_income = sum(self.normalize_number(op_income_row.get(col, 0)) for col in value_cols)
            revenue = sum(self.normalize_number(revenue_row.get(col, 0)) for col in value_cols)
            if revenue > 0:
                op_margin = op_income / revenue
                results['income_statement_4'] = -0.2 <= op_margin <= 0.5  # -20% to 50% is reasonable
            else:
                results['income_statement_4'] = False
        else:
            results['income_statement_4'] = False
        
        # Check 5: Interest expense coverage adequate
        interest_row = self.find_row_by_description(income_statement, ['Interest expense', 'Interest'])
        op_income_row = self.find_row_by_description(income_statement, ['Income from operations', 'Operating income'])
        
        if interest_row and op_income_row:
            interest = sum(self.normalize_number(interest_row.get(col, 0)) for col in value_cols)
            op_income = sum(self.normalize_number(op_income_row.get(col, 0)) for col in value_cols)
            if interest > 0:
                coverage_ratio = op_income / interest
                results['income_statement_5'] = coverage_ratio >= 1.5  # Coverage ratio should be at least 1.5
            else:
                results['income_statement_5'] = True  # No interest expense is good
        else:
            results['income_statement_5'] = True  # No interest expense
        
        # Check 6: Tax rate reasonable
        tax_row = self.find_row_by_description(income_statement, ['Provision for income taxes', 'Income taxes'])
        net_income_row = self.find_row_by_description(income_statement, ['Net income'])
        
        if tax_row and net_income_row:
            tax = sum(self.normalize_number(tax_row.get(col, 0)) for col in value_cols)
            net_income = sum(self.normalize_number(net_income_row.get(col, 0)) for col in value_cols)
            if net_income > 0:
                tax_rate = tax / (tax + net_income)  # Effective tax rate
                results['income_statement_6'] = 0.1 <= tax_rate <= 0.5  # 10-50% is reasonable
            else:
                results['income_statement_6'] = False
        else:
            results['income_statement_6'] = False
        
        # Check 7: Net income growth sustainable (simplified - just check if positive)
        net_income_row = self.find_row_by_description(income_statement, ['Net income'])
        if net_income_row:
            net_income = sum(self.normalize_number(net_income_row.get(col, 0)) for col in value_cols)
            results['income_statement_7'] = net_income > 0  # Positive net income is sustainable
        else:
            results['income_statement_7'] = False
        
        # Check 8: EPS calculations accurate (simplified - just check if EPS exists)
        eps_row = self.find_row_by_description(income_statement, ['Basic net income per share', 'Diluted net income per share'])
        results['income_statement_8'] = eps_row is not None
        
        return results
    
    def validate_cash_flow_checks(self) -> Dict[str, bool]:
        """
        Perform cash flow statement validation checks.
        
        Returns:
            Dict with check results
        """
        cash_flow = self.get_statement_by_name('CASH')
        if not cash_flow:
            return {f'cash_flow_{i}': False for i in range(1, 9)}
        
        value_cols = self.get_value_columns(cash_flow)
        results = {}
        
        # Check 1: Operating cash flow positive
        op_cf_row = self.find_row_by_description(cash_flow, ['Net cash provided by operating activities'])
        if op_cf_row:
            op_cf = sum(self.normalize_number(op_cf_row.get(col, 0)) for col in value_cols)
            results['cash_flow_1'] = op_cf > 0
        else:
            results['cash_flow_1'] = False
        
        # Check 2: Operating cash flow > Net income
        op_cf_row = self.find_row_by_description(cash_flow, ['Net cash provided by operating activities'])
        net_income_row = self.find_row_by_description(cash_flow, ['Net income'])
        
        if op_cf_row and net_income_row:
            op_cf = sum(self.normalize_number(op_cf_row.get(col, 0)) for col in value_cols)
            net_income = sum(self.normalize_number(net_income_row.get(col, 0)) for col in value_cols)
            results['cash_flow_2'] = op_cf > net_income
        else:
            results['cash_flow_2'] = False
        
        # Check 3: Capital expenditures reasonable
        capex_row = self.find_row_by_description(cash_flow, ['Purchases of property and equipment'])
        op_cf_row = self.find_row_by_description(cash_flow, ['Net cash provided by operating activities'])
        
        if capex_row and op_cf_row:
            capex = abs(sum(self.normalize_number(capex_row.get(col, 0)) for col in value_cols))
            op_cf = sum(self.normalize_number(op_cf_row.get(col, 0)) for col in value_cols)
            if op_cf > 0:
                capex_ratio = capex / op_cf
                results['cash_flow_3'] = capex_ratio <= 1.0  # Capex should not exceed operating cash flow
            else:
                results['cash_flow_3'] = False
        else:
            results['cash_flow_3'] = True  # No capex is fine
        
        # Check 4: Free cash flow positive
        op_cf_row = self.find_row_by_description(cash_flow, ['Net cash provided by operating activities'])
        capex_row = self.find_row_by_description(cash_flow, ['Purchases of property and equipment'])
        
        if op_cf_row and capex_row:
            op_cf = sum(self.normalize_number(op_cf_row.get(col, 0)) for col in value_cols)
            capex = abs(sum(self.normalize_number(capex_row.get(col, 0)) for col in value_cols))
            fcf = op_cf - capex
            results['cash_flow_4'] = fcf > 0
        else:
            results['cash_flow_4'] = False
        
        # Check 5: Dividend payments sustainable
        dividend_row = self.find_row_by_description(cash_flow, ['Dividend payments'])
        op_cf_row = self.find_row_by_description(cash_flow, ['Net cash provided by operating activities'])
        
        if dividend_row and op_cf_row:
            dividends = abs(sum(self.normalize_number(dividend_row.get(col, 0)) for col in value_cols))
            op_cf = sum(self.normalize_number(op_cf_row.get(col, 0)) for col in value_cols)
            if op_cf > 0:
                dividend_ratio = dividends / op_cf
                results['cash_flow_5'] = dividend_ratio <= 0.5  # Dividends should not exceed 50% of operating cash flow
            else:
                results['cash_flow_5'] = False
        else:
            results['cash_flow_5'] = True  # No dividends is fine
        
        # Check 6: Share repurchases appropriate
        repurchase_row = self.find_row_by_description(cash_flow, ['Repurchases of stock'])
        op_cf_row = self.find_row_by_description(cash_flow, ['Net cash provided by operating activities'])
        
        if repurchase_row and op_cf_row:
            repurchases = abs(sum(self.normalize_number(repurchase_row.get(col, 0)) for col in value_cols))
            op_cf = sum(self.normalize_number(op_cf_row.get(col, 0)) for col in value_cols)
            if op_cf > 0:
                repurchase_ratio = repurchases / op_cf
                results['cash_flow_6'] = repurchase_ratio <= 0.7  # Repurchases should not exceed 70% of operating cash flow
            else:
                results['cash_flow_6'] = False
        else:
            results['cash_flow_6'] = True  # No repurchases is fine
        
        # Check 7: Debt issuance/repayment reasonable
        debt_keywords = ['Proceeds from issuance of debt', 'Repayments of debt']
        total_debt_activity = 0
        for keyword in debt_keywords:
            debt_row = self.find_row_by_description(cash_flow, [keyword])
            if debt_row:
                total_debt_activity += abs(sum(self.normalize_number(debt_row.get(col, 0)) for col in value_cols))
        
        op_cf_row = self.find_row_by_description(cash_flow, ['Net cash provided by operating activities'])
        if op_cf_row and total_debt_activity > 0:
            op_cf = sum(self.normalize_number(op_cf_row.get(col, 0)) for col in value_cols)
            if op_cf > 0:
                debt_ratio = total_debt_activity / op_cf
                results['cash_flow_7'] = debt_ratio <= 1.0  # Debt activity should not exceed operating cash flow
            else:
                results['cash_flow_7'] = False
        else:
            results['cash_flow_7'] = True  # No debt activity is fine
        
        # Check 8: Cash balance changes logical
        cash_end_row = self.find_row_by_description(cash_flow, ['Cash and cash equivalents at end of period'])
        cash_begin_row = self.find_row_by_description(cash_flow, ['Cash and cash equivalents at beginning of period'])
        
        if cash_end_row and cash_begin_row:
            cash_end = sum(self.normalize_number(cash_end_row.get(col, 0)) for col in value_cols)
            cash_begin = sum(self.normalize_number(cash_begin_row.get(col, 0)) for col in value_cols)
            cash_change = cash_end - cash_begin
            results['cash_flow_8'] = abs(cash_change) < 1000000  # Cash change should be reasonable
        else:
            results['cash_flow_8'] = False
        
        return results
    
    def validate_cross_statement_checks(self) -> Dict[str, bool]:
        """
        Perform cross-statement validation checks.
        
        Returns:
            Dict with check results
        """
        balance_sheet = self.get_statement_by_name('BALANCE')
        income_statement = self.get_statement_by_name('INCOME')
        cash_flow = self.get_statement_by_name('CASH')
        
        results = {}
        
        # Check 1: Net income flows to retained earnings
        if income_statement and balance_sheet:
            net_income_row = self.find_row_by_description(income_statement, ['Net income'])
            re_row = self.find_row_by_description(balance_sheet, ['Retained earnings'])
            
            if net_income_row and re_row:
                net_income = sum(self.normalize_number(net_income_row.get(col, 0)) for col in self.get_value_columns(income_statement))
                re_value = sum(self.normalize_number(re_row.get(col, 0)) for col in self.get_value_columns(balance_sheet))
                results['cross_statement_1'] = net_income > 0 and re_value > 0
            else:
                results['cross_statement_1'] = False
        else:
            results['cross_statement_1'] = False
        
        # Check 2: Depreciation consistent across statements
        if income_statement and cash_flow:
            dep_income = self.find_row_by_description(income_statement, ['Depreciation'])
            dep_cf = self.find_row_by_description(cash_flow, ['Depreciation'])
            results['cross_statement_2'] = dep_income is not None and dep_cf is not None
        else:
            results['cross_statement_2'] = False
        
        # Check 3: Dividends reduce retained earnings (simplified)
        if cash_flow and balance_sheet:
            dividend_row = self.find_row_by_description(cash_flow, ['Dividend payments'])
            re_row = self.find_row_by_description(balance_sheet, ['Retained earnings'])
            results['cross_statement_3'] = dividend_row is not None or re_row is not None
        else:
            results['cross_statement_3'] = False
        
        # Check 4: Capital expenditures increase PP&E (simplified)
        if cash_flow and balance_sheet:
            capex_row = self.find_row_by_description(cash_flow, ['Purchases of property and equipment'])
            ppe_row = self.find_row_by_description(balance_sheet, ['Property and equipment'])
            results['cross_statement_4'] = capex_row is not None and ppe_row is not None
        else:
            results['cross_statement_4'] = False
        
        # Check 5: Debt changes reflected in both statements
        if cash_flow and balance_sheet:
            debt_cf_keywords = ['Proceeds from issuance of debt', 'Repayments of debt']
            debt_bs_keywords = ['Long-term debt', 'Total liabilities']
            
            has_debt_cf = any(self.find_row_by_description(cash_flow, [keyword]) for keyword in debt_cf_keywords)
            has_debt_bs = any(self.find_row_by_description(balance_sheet, [keyword]) for keyword in debt_bs_keywords)
            results['cross_statement_5'] = has_debt_cf and has_debt_bs
        else:
            results['cross_statement_5'] = False
        
        # Check 6: Working capital changes consistent
        if balance_sheet:
            current_assets = self.find_row_by_description(balance_sheet, ['Total current assets'])
            current_liab = self.find_row_by_description(balance_sheet, ['Total current liabilities'])
            results['cross_statement_6'] = current_assets is not None and current_liab is not None
        else:
            results['cross_statement_6'] = False
        
        # Check 7: Tax payments align with tax expense
        if income_statement and cash_flow:
            tax_income = self.find_row_by_description(income_statement, ['Provision for income taxes'])
            tax_cf = self.find_row_by_description(cash_flow, ['Income taxes, net'])
            results['cross_statement_7'] = tax_income is not None and tax_cf is not None
        else:
            results['cross_statement_7'] = False
        
        # Check 8: Stock-based compensation properly recorded
        if income_statement and cash_flow:
            sbc_income = self.find_row_by_description(income_statement, ['Stock-based compensation'])
            sbc_cf = self.find_row_by_description(cash_flow, ['Stock-based compensation'])
            results['cross_statement_8'] = sbc_income is not None or sbc_cf is not None
        else:
            results['cross_statement_8'] = False
        
        return results
    
    def validate_all_checks(self) -> Dict[str, Any]:
        """
        Perform all validation checks and return results.
        
        Returns:
            Dict with all check results and summary statistics
        """
        balance_checks = self.validate_balance_sheet_checks()
        income_checks = self.validate_income_statement_checks()
        cash_flow_checks = self.validate_cash_flow_checks()
        cross_statement_checks = self.validate_cross_statement_checks()
        
        # Calculate totals for balance sheet verification
        balance_sheet = self.get_statement_by_name('BALANCE')
        total_assets = self.calculate_total_assets(balance_sheet) if balance_sheet else None
        total_liab_equity = self.calculate_total_liabilities_equity(balance_sheet) if balance_sheet else None
        
        # Combine all results
        all_results = {
            **balance_checks,
            **income_checks,
            **cash_flow_checks,
            **cross_statement_checks
        }
        
        # Calculate summary statistics
        total_checks = len(all_results)
        passed_checks = sum(all_results.values())
        pass_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        return {
            'checklist_results': all_results,
            'summary': {
                'total_checks': total_checks,
                'passed_checks': passed_checks,
                'failed_checks': total_checks - passed_checks,
                'pass_rate': round(pass_rate, 1)
            },
            'balance_sheet_totals': {
                'assets': total_assets,
                'liabilities_equity': total_liab_equity
            } if balance_sheet else None
        }


def validate_financial_statements(statements_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Main function to validate financial statements.
    
    Args:
        statements_data: List of statement dictionaries from extraction
        
    Returns:
        Dict with validation results
    """
    validator = FinancialStatementValidator(statements_data)
    return validator.validate_all_checks()


if __name__ == '__main__':
    # Example usage
    sample_data = [
        {
            "name": "BALANCE_SHEETS",
            "pageNumber": 5,
            "headers": ["Description", "As of December 31, 2024", "As of March 31, 2025"],
            "tableData": [
                {"Description": "Assets", "As of December 31, 2024": "", "As of March 31, 2025": ""},
                {"Description": "Cash and cash equivalents", "As of December 31, 2024": "23466", "As of March 31, 2025": "23264"},
                {"Description": "Total assets", "As of December 31, 2024": "450256", "As of March 31, 2025": "475374"}
            ]
        }
    ]
    
    results = validate_financial_statements(sample_data)
    print(json.dumps(results, indent=2)) 