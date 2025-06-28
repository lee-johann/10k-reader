package com.pdfreader.service;

import com.pdfreader.model.ProcessingResult;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import org.springframework.http.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

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
    private static final String PYTHON_API_BASE_URL = "http://localhost:5001";
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final RestTemplate restTemplate = new RestTemplate();

    public List<String> getAvailablePdfs() {
        try {
            // Call Python API to get available documents
            String url = PYTHON_API_BASE_URL + "/api/list-documents";
            ResponseEntity<Map> response = restTemplate.getForEntity(url, Map.class);

            if (response.getStatusCode() == HttpStatus.OK && response.getBody() != null) {
                Map<String, Object> responseBody = response.getBody();
                if (Boolean.TRUE.equals(responseBody.get("success"))) {
                    @SuppressWarnings("unchecked")
                    List<String> documents = (List<String>) responseBody.get("documents");
                    return documents != null ? documents : new ArrayList<>();
                }
            }
        } catch (Exception e) {
            System.err.println("Error calling Python API for documents: " + e.getMessage());
        }

        // Fallback to local directory scanning
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
            System.err.println("Error reading documents directory: " + e.getMessage());
        }
        return pdfFiles;
    }

    public ProcessingResult processPdfFromDocuments(String filename) throws IOException {
        try {
            // Create output directory if it doesn't exist
            createDirectories();

            // Check if file exists in documents folder
            Path pdfPath = Paths.get(DOCUMENTS_DIR, filename);
            if (!Files.exists(pdfPath)) {
                return new ProcessingResult(null, null, "PDF file not found: " + filename, false);
            }

            // Call Python API to process PDF from path
            String url = PYTHON_API_BASE_URL + "/api/process-pdf-from-path";

            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("pdf_path", pdfPath.toString());
            requestBody.put("output_dir", OUTPUT_DIR);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);

            HttpEntity<Map<String, Object>> requestEntity = new HttpEntity<>(requestBody, headers);

            ResponseEntity<Map> response = restTemplate.postForEntity(url, requestEntity, Map.class);

            if (response.getStatusCode() == HttpStatus.OK && response.getBody() != null) {
                Map<String, Object> responseBody = response.getBody();
                if (Boolean.TRUE.equals(responseBody.get("success"))) {
                    return parseApiResponse(responseBody);
                } else {
                    String error = (String) responseBody.get("error");
                    return new ProcessingResult(null, null, "Python API error: " + error, false);
                }
            } else {
                return new ProcessingResult(null, null, "Python API returned status: " + response.getStatusCode(),
                        false);
            }

        } catch (Exception e) {
            return new ProcessingResult(null, null, "Error processing PDF: " + e.getMessage(), false);
        }
    }

    public ProcessingResult processPdf(MultipartFile file) throws IOException {
        try {
            // Create directories if they don't exist
            createDirectories();

            // Call Python API to process uploaded PDF
            String url = PYTHON_API_BASE_URL + "/api/process-pdf";

            // Prepare multipart request
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);

            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            body.add("file", new ByteArrayResource(file.getBytes()) {
                @Override
                public String getFilename() {
                    return file.getOriginalFilename();
                }
            });
            body.add("output_dir", OUTPUT_DIR);

            HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);

            ResponseEntity<Map> response = restTemplate.postForEntity(url, requestEntity, Map.class);

            if (response.getStatusCode() == HttpStatus.OK && response.getBody() != null) {
                Map<String, Object> responseBody = response.getBody();
                if (Boolean.TRUE.equals(responseBody.get("success"))) {
                    ProcessingResult result = parseApiResponse(responseBody);

                    // Set the PDF URL for uploaded files
                    String originalFilename = file.getOriginalFilename();
                    String savedFilename = System.currentTimeMillis() + "_" + originalFilename;
                    result.setPdfUrl("/uploads/" + savedFilename);

                    return result;
                } else {
                    String error = (String) responseBody.get("error");
                    return new ProcessingResult(null, null, "Python API error: " + error, false);
                }
            } else {
                return new ProcessingResult(null, null, "Python API returned status: " + response.getStatusCode(),
                        false);
            }

        } catch (Exception e) {
            return new ProcessingResult(null, null, "Error processing PDF: " + e.getMessage(), false);
        }
    }

    private void createDirectories() throws IOException {
        Files.createDirectories(Paths.get(OUTPUT_DIR));
    }

    private ProcessingResult parseApiResponse(Map<String, Object> responseBody) throws IOException {
        List<ProcessingResult.StatementData> statements = new ArrayList<>();
        ProcessingResult.ValidationData validationData = null;

        try {
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> statementsList = (List<Map<String, Object>>) responseBody.get("statements");

            if (statementsList != null) {
                for (Map<String, Object> statementData : statementsList) {
                    String name = (String) statementData.get("name");
                    // Handle pageNumber as either Integer or String
                    Integer pageNumber;
                    Object pageNumberObj = statementData.get("pageNumber");
                    if (pageNumberObj instanceof Integer) {
                        pageNumber = (Integer) pageNumberObj;
                    } else if (pageNumberObj instanceof String) {
                        pageNumber = Integer.parseInt((String) pageNumberObj);
                    } else {
                        pageNumber = 0; // Default fallback
                    }

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
            Map<String, Object> validationMap = (Map<String, Object>) responseBody.get("validation");

            if (validationMap != null) {
                validationData = parseValidationData(validationMap);
            }

        } catch (Exception e) {
            throw new IOException("Failed to parse API response: " + e.getMessage(), e);
        }

        String message = (String) responseBody.get("message");
        if (message == null) {
            message = "Processing completed successfully";
        }

        return new ProcessingResult(null, statements, message, true, validationData);
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
            // Handle numeric values that might be Integer, Double, or String
            int totalChecks = getIntValue(summaryMap.get("total_checks"));
            int passedChecks = getIntValue(summaryMap.get("passed_checks"));
            int failedChecks = getIntValue(summaryMap.get("failed_checks"));
            double passRate = getDoubleValue(summaryMap.get("pass_rate"));

            summary = new ProcessingResult.ValidationSummary(totalChecks, passedChecks, failedChecks, passRate);
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
                        getDoubleValue(assetsMap.get("calculated")),
                        getDoubleValue(assetsMap.get("reported")),
                        getDoubleValue(assetsMap.get("difference")),
                        (Boolean) assetsMap.get("matches"));
            }

            @SuppressWarnings("unchecked")
            Map<String, Object> liabilitiesEquityMap = (Map<String, Object>) balanceSheetTotalsMap
                    .get("liabilities_equity");
            if (liabilitiesEquityMap != null) {
                liabilitiesEquity = new ProcessingResult.TotalData(
                        getDoubleValue(liabilitiesEquityMap.get("calculated")),
                        getDoubleValue(liabilitiesEquityMap.get("reported")),
                        getDoubleValue(liabilitiesEquityMap.get("difference")),
                        (Boolean) liabilitiesEquityMap.get("matches"));
            }

            balanceSheetTotals = new ProcessingResult.BalanceSheetTotals(assets, liabilitiesEquity);
        }

        return new ProcessingResult.ValidationData(checklistResults, summary, balanceSheetTotals);
    }

    // Helper method to safely convert Object to int
    private int getIntValue(Object value) {
        if (value instanceof Integer) {
            return (Integer) value;
        } else if (value instanceof Double) {
            return ((Double) value).intValue();
        } else if (value instanceof String) {
            try {
                return Integer.parseInt((String) value);
            } catch (NumberFormatException e) {
                return 0;
            }
        }
        return 0;
    }

    // Helper method to safely convert Object to double
    private double getDoubleValue(Object value) {
        if (value instanceof Double) {
            return (Double) value;
        } else if (value instanceof Integer) {
            return ((Integer) value).doubleValue();
        } else if (value instanceof String) {
            try {
                return Double.parseDouble((String) value);
            } catch (NumberFormatException e) {
                return 0.0;
            }
        }
        return 0.0;
    }
}