package com.pdfreader.service;

import com.pdfreader.model.ProcessingResult;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class PdfProcessingService {

    private static final String DOCUMENTS_DIR = "../documents";
    private static final String OUTPUT_DIR = "output";
    private final ObjectMapper objectMapper = new ObjectMapper();

    public List<String> getAvailablePdfs() {
        List<String> pdfFiles = new ArrayList<>();
        try {
            File documentsDir = new File(DOCUMENTS_DIR);
            if (documentsDir.exists() && documentsDir.isDirectory()) {
                File[] files = documentsDir.listFiles((dir, name) -> name.toLowerCase().endsWith(".pdf"));
                if (files != null) {
                    for (File file : files) {
                        pdfFiles.add(file.getName());
                    }
                }
            }
        } catch (Exception e) {
            // Log error but return empty list
            System.err.println("Error reading documents directory: " + e.getMessage());
        }
        return pdfFiles;
    }

    public ProcessingResult processPdfFromDocuments(String filename) throws IOException {
        // Create output directory if it doesn't exist
        createDirectories();

        // Check if file exists in documents folder
        Path pdfPath = Paths.get(DOCUMENTS_DIR, filename);
        if (!Files.exists(pdfPath)) {
            return new ProcessingResult(null, null, "PDF file not found: " + filename, false);
        }

        try {
            // Run Python script to extract all statements
            ProcessBuilder processBuilder = new ProcessBuilder(
                    "python3", "pdf_processor.py", "documents/" + filename, OUTPUT_DIR, filename.replace(".pdf", ""));
            processBuilder.directory(new File(".."));

            Process process = processBuilder.start();

            // Capture stdout (JSON) and stderr (log messages) separately
            BufferedReader stdoutReader = new BufferedReader(new InputStreamReader(process.getInputStream()));
            BufferedReader stderrReader = new BufferedReader(new InputStreamReader(process.getErrorStream()));

            StringBuilder jsonOutput = new StringBuilder();
            StringBuilder logOutput = new StringBuilder();

            // Read stdout (JSON data)
            String line;
            while ((line = stdoutReader.readLine()) != null) {
                jsonOutput.append(line).append("\n");
            }

            // Read stderr (log messages) - just for logging, not for parsing
            while ((line = stderrReader.readLine()) != null) {
                logOutput.append(line).append("\n");
            }

            int exitCode = process.waitFor();

            if (exitCode != 0) {
                return new ProcessingResult(null, null, "Python script failed: " + logOutput.toString(), false);
            }

            // Parse JSON response from Python script (stdout only)
            ProcessingResult result = parseJsonFromOutput(jsonOutput.toString());

            return result;

        } catch (Exception e) {
            return new ProcessingResult(null, null, "Error processing PDF: " + e.getMessage(), false);
        }
    }

    // Keep the old method for backward compatibility
    public ProcessingResult processPdf(MultipartFile file) throws IOException {
        // Create directories if they don't exist
        createDirectories();

        // Save uploaded file
        String originalFilename = file.getOriginalFilename();
        String savedFilename = System.currentTimeMillis() + "_" + originalFilename;
        Path uploadPath = Paths.get("uploads", savedFilename);
        Files.createDirectories(Paths.get("uploads"));
        Files.copy(file.getInputStream(), uploadPath);

        try {
            // Run Python script to extract all statements
            ProcessBuilder processBuilder = new ProcessBuilder(
                    "python3", "pdf_processor.py", uploadPath.toString(), OUTPUT_DIR,
                    originalFilename.replace(".pdf", ""));
            processBuilder.directory(new File(".."));

            Process process = processBuilder.start();

            // Capture stdout (JSON) and stderr (log messages) separately
            BufferedReader stdoutReader = new BufferedReader(new InputStreamReader(process.getInputStream()));
            BufferedReader stderrReader = new BufferedReader(new InputStreamReader(process.getErrorStream()));

            StringBuilder jsonOutput = new StringBuilder();
            StringBuilder logOutput = new StringBuilder();

            // Read stdout (JSON data)
            String line;
            while ((line = stdoutReader.readLine()) != null) {
                jsonOutput.append(line).append("\n");
            }

            // Read stderr (log messages) - just for logging, not for parsing
            while ((line = stderrReader.readLine()) != null) {
                logOutput.append(line).append("\n");
            }

            int exitCode = process.waitFor();

            if (exitCode != 0) {
                return new ProcessingResult(null, null, "Python script failed: " + logOutput.toString(), false);
            }

            // Parse JSON response from Python script (stdout only)
            ProcessingResult result = parseJsonFromOutput(jsonOutput.toString());

            // Set the PDF URL for uploaded files
            result.setPdfUrl("/uploads/" + savedFilename);

            return result;

        } catch (Exception e) {
            return new ProcessingResult(null, null, "Error processing PDF: " + e.getMessage(), false);
        }
    }

    private void createDirectories() throws IOException {
        Files.createDirectories(Paths.get(OUTPUT_DIR));
    }

    private ProcessingResult parseJsonFromOutput(String jsonOutput) throws IOException {
        List<ProcessingResult.StatementData> statements = new ArrayList<>();
        ProcessingResult.ValidationData validationData = null;

        try {
            // Parse the JSON response
            Map<String, Object> jsonResponse = objectMapper.readValue(jsonOutput,
                    new TypeReference<Map<String, Object>>() {
                    });

            @SuppressWarnings("unchecked")
            List<Map<String, Object>> statementsList = (List<Map<String, Object>>) jsonResponse.get("statements");

            if (statementsList != null) {
                for (Map<String, Object> statementData : statementsList) {
                    String name = (String) statementData.get("name");
                    Integer pageNumber = (Integer) statementData.get("pageNumber");

                    @SuppressWarnings("unchecked")
                    List<String> headers = (List<String>) statementData.get("headers");

                    @SuppressWarnings("unchecked")
                    List<Map<String, Object>> tableDataList = (List<Map<String, Object>>) statementData
                            .get("tableData");

                    List<Map<String, String>> tableData = new ArrayList<>();
                    if (tableDataList != null) {
                        for (Map<String, Object> row : tableDataList) {
                            Map<String, String> stringRow = new HashMap<>();
                            for (Map.Entry<String, Object> entry : row.entrySet()) {
                                stringRow.put(entry.getKey(),
                                        entry.getValue() != null ? entry.getValue().toString() : "");
                            }
                            tableData.add(stringRow);
                        }
                    }

                    statements.add(new ProcessingResult.StatementData(name, pageNumber, tableData, headers));
                }
            }

            // Parse validation data
            @SuppressWarnings("unchecked")
            Map<String, Object> validationMap = (Map<String, Object>) jsonResponse.get("validation");

            if (validationMap != null) {
                validationData = parseValidationData(validationMap);
            }

        } catch (Exception e) {
            throw new IOException("Failed to parse JSON response: " + e.getMessage(), e);
        }

        return new ProcessingResult(null, statements, "Processing completed successfully", true, validationData);
    }

    private ProcessingResult.ValidationData parseValidationData(Map<String, Object> validationMap) {
        // Parse checklist results
        @SuppressWarnings("unchecked")
        Map<String, Object> checklistResultsMap = (Map<String, Object>) validationMap.get("checklist_results");
        Map<String, Boolean> checklistResults = new HashMap<>();

        if (checklistResultsMap != null) {
            for (Map.Entry<String, Object> entry : checklistResultsMap.entrySet()) {
                checklistResults.put(entry.getKey(), (Boolean) entry.getValue());
            }
        }

        // Parse summary
        @SuppressWarnings("unchecked")
        Map<String, Object> summaryMap = (Map<String, Object>) validationMap.get("summary");
        ProcessingResult.ValidationSummary summary = null;

        if (summaryMap != null) {
            summary = new ProcessingResult.ValidationSummary(
                    ((Number) summaryMap.get("total_checks")).intValue(),
                    ((Number) summaryMap.get("passed_checks")).intValue(),
                    ((Number) summaryMap.get("failed_checks")).intValue(),
                    ((Number) summaryMap.get("pass_rate")).doubleValue());
        }

        // Parse balance sheet totals
        @SuppressWarnings("unchecked")
        Map<String, Object> balanceSheetTotalsMap = (Map<String, Object>) validationMap.get("balance_sheet_totals");
        ProcessingResult.BalanceSheetTotals balanceSheetTotals = null;

        if (balanceSheetTotalsMap != null) {
            ProcessingResult.TotalData assets = null;
            ProcessingResult.TotalData liabilitiesEquity = null;

            @SuppressWarnings("unchecked")
            Map<String, Object> assetsMap = (Map<String, Object>) balanceSheetTotalsMap.get("assets");
            if (assetsMap != null) {
                assets = new ProcessingResult.TotalData(
                        ((Number) assetsMap.get("calculated")).doubleValue(),
                        ((Number) assetsMap.get("reported")).doubleValue(),
                        ((Number) assetsMap.get("difference")).doubleValue(),
                        (Boolean) assetsMap.get("matches"));
            }

            @SuppressWarnings("unchecked")
            Map<String, Object> liabilitiesEquityMap = (Map<String, Object>) balanceSheetTotalsMap
                    .get("liabilities_equity");
            if (liabilitiesEquityMap != null) {
                liabilitiesEquity = new ProcessingResult.TotalData(
                        ((Number) liabilitiesEquityMap.get("calculated")).doubleValue(),
                        ((Number) liabilitiesEquityMap.get("reported")).doubleValue(),
                        ((Number) liabilitiesEquityMap.get("difference")).doubleValue(),
                        (Boolean) liabilitiesEquityMap.get("matches"));
            }

            balanceSheetTotals = new ProcessingResult.BalanceSheetTotals(assets, liabilitiesEquity);
        }

        return new ProcessingResult.ValidationData(checklistResults, summary, balanceSheetTotals);
    }
}