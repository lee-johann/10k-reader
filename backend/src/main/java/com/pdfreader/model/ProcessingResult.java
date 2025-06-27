package com.pdfreader.model;

import java.util.List;
import java.util.Map;

public class ProcessingResult {
    private String pdfUrl;
    private List<StatementData> statements;
    private String message;
    private boolean success;
    private ValidationData validation;

    public ProcessingResult() {
    }

    public ProcessingResult(String pdfUrl, List<StatementData> statements, String message, boolean success) {
        this.pdfUrl = pdfUrl;
        this.statements = statements;
        this.message = message;
        this.success = success;
    }

    public ProcessingResult(String pdfUrl, List<StatementData> statements, String message, boolean success,
            ValidationData validation) {
        this.pdfUrl = pdfUrl;
        this.statements = statements;
        this.message = message;
        this.success = success;
        this.validation = validation;
    }

    // Getters and Setters
    public String getPdfUrl() {
        return pdfUrl;
    }

    public void setPdfUrl(String pdfUrl) {
        this.pdfUrl = pdfUrl;
    }

    public List<StatementData> getStatements() {
        return statements;
    }

    public void setStatements(List<StatementData> statements) {
        this.statements = statements;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public ValidationData getValidation() {
        return validation;
    }

    public void setValidation(ValidationData validation) {
        this.validation = validation;
    }

    public static class StatementData {
        private String name;
        private int pageNumber;
        private List<Map<String, String>> tableData;
        private List<String> headers;

        public StatementData() {
        }

        public StatementData(String name, int pageNumber, List<Map<String, String>> tableData, List<String> headers) {
            this.name = name;
            this.pageNumber = pageNumber;
            this.tableData = tableData;
            this.headers = headers;
        }

        // Getters and Setters
        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public int getPageNumber() {
            return pageNumber;
        }

        public void setPageNumber(int pageNumber) {
            this.pageNumber = pageNumber;
        }

        public List<Map<String, String>> getTableData() {
            return tableData;
        }

        public void setTableData(List<Map<String, String>> tableData) {
            this.tableData = tableData;
        }

        public List<String> getHeaders() {
            return headers;
        }

        public void setHeaders(List<String> headers) {
            this.headers = headers;
        }
    }

    public static class ValidationData {
        private Map<String, Boolean> checklistResults;
        private ValidationSummary summary;
        private BalanceSheetTotals balanceSheetTotals;

        public ValidationData() {
        }

        public ValidationData(Map<String, Boolean> checklistResults, ValidationSummary summary,
                BalanceSheetTotals balanceSheetTotals) {
            this.checklistResults = checklistResults;
            this.summary = summary;
            this.balanceSheetTotals = balanceSheetTotals;
        }

        // Getters and Setters
        public Map<String, Boolean> getChecklistResults() {
            return checklistResults;
        }

        public void setChecklistResults(Map<String, Boolean> checklistResults) {
            this.checklistResults = checklistResults;
        }

        public ValidationSummary getSummary() {
            return summary;
        }

        public void setSummary(ValidationSummary summary) {
            this.summary = summary;
        }

        public BalanceSheetTotals getBalanceSheetTotals() {
            return balanceSheetTotals;
        }

        public void setBalanceSheetTotals(BalanceSheetTotals balanceSheetTotals) {
            this.balanceSheetTotals = balanceSheetTotals;
        }
    }

    public static class ValidationSummary {
        private int totalChecks;
        private int passedChecks;
        private int failedChecks;
        private double passRate;

        public ValidationSummary() {
        }

        public ValidationSummary(int totalChecks, int passedChecks, int failedChecks, double passRate) {
            this.totalChecks = totalChecks;
            this.passedChecks = passedChecks;
            this.failedChecks = failedChecks;
            this.passRate = passRate;
        }

        // Getters and Setters
        public int getTotalChecks() {
            return totalChecks;
        }

        public void setTotalChecks(int totalChecks) {
            this.totalChecks = totalChecks;
        }

        public int getPassedChecks() {
            return passedChecks;
        }

        public void setPassedChecks(int passedChecks) {
            this.passedChecks = passedChecks;
        }

        public int getFailedChecks() {
            return failedChecks;
        }

        public void setFailedChecks(int failedChecks) {
            this.failedChecks = failedChecks;
        }

        public double getPassRate() {
            return passRate;
        }

        public void setPassRate(double passRate) {
            this.passRate = passRate;
        }
    }

    public static class BalanceSheetTotals {
        private TotalData assets;
        private TotalData liabilitiesEquity;

        public BalanceSheetTotals() {
        }

        public BalanceSheetTotals(TotalData assets, TotalData liabilitiesEquity) {
            this.assets = assets;
            this.liabilitiesEquity = liabilitiesEquity;
        }

        // Getters and Setters
        public TotalData getAssets() {
            return assets;
        }

        public void setAssets(TotalData assets) {
            this.assets = assets;
        }

        public TotalData getLiabilitiesEquity() {
            return liabilitiesEquity;
        }

        public void setLiabilitiesEquity(TotalData liabilitiesEquity) {
            this.liabilitiesEquity = liabilitiesEquity;
        }
    }

    public static class TotalData {
        private double calculated;
        private double reported;
        private double difference;
        private boolean matches;

        public TotalData() {
        }

        public TotalData(double calculated, double reported, double difference, boolean matches) {
            this.calculated = calculated;
            this.reported = reported;
            this.difference = difference;
            this.matches = matches;
        }

        // Getters and Setters
        public double getCalculated() {
            return calculated;
        }

        public void setCalculated(double calculated) {
            this.calculated = calculated;
        }

        public double getReported() {
            return reported;
        }

        public void setReported(double reported) {
            this.reported = reported;
        }

        public double getDifference() {
            return difference;
        }

        public void setDifference(double difference) {
            this.difference = difference;
        }

        public boolean isMatches() {
            return matches;
        }

        public void setMatches(boolean matches) {
            this.matches = matches;
        }
    }
}