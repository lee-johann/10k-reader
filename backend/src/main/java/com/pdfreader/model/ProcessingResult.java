package com.pdfreader.model;

import java.util.List;
import java.util.Map;

public class ProcessingResult {
    private String pdfUrl;
    private List<StatementData> statements;
    private String message;
    private boolean success;

    public ProcessingResult() {}

    public ProcessingResult(String pdfUrl, List<StatementData> statements, String message, boolean success) {
        this.pdfUrl = pdfUrl;
        this.statements = statements;
        this.message = message;
        this.success = success;
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

    public static class StatementData {
        private String name;
        private int pageNumber;
        private List<Map<String, String>> tableData;
        private List<String> headers;

        public StatementData() {}

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
} 