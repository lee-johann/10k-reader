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
                "python3", "pdf_processor.py", "documents/" + filename, OUTPUT_DIR, filename.replace(".pdf", "")
            );
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
            List<ProcessingResult.StatementData> statements = parseJsonFromOutput(jsonOutput.toString());
            
            return new ProcessingResult(
                null,
                statements,
                "Processing completed successfully",
                true
            );

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
                "python3", "pdf_processor.py", uploadPath.toString(), OUTPUT_DIR, originalFilename.replace(".pdf", "")
            );
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
            List<ProcessingResult.StatementData> statements = parseJsonFromOutput(jsonOutput.toString());
            
            return new ProcessingResult(
                "/uploads/" + savedFilename,
                statements,
                "Processing completed successfully",
                true
            );

        } catch (Exception e) {
            return new ProcessingResult(null, null, "Error processing PDF: " + e.getMessage(), false);
        }
    }

    private void createDirectories() throws IOException {
        Files.createDirectories(Paths.get(OUTPUT_DIR));
    }

    private List<ProcessingResult.StatementData> parseJsonFromOutput(String jsonOutput) throws IOException {
        List<ProcessingResult.StatementData> statements = new ArrayList<>();
        
        try {
            // Parse the JSON response
            Map<String, Object> jsonResponse = objectMapper.readValue(jsonOutput, new TypeReference<Map<String, Object>>() {});
            
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> statementsList = (List<Map<String, Object>>) jsonResponse.get("statements");
            
            if (statementsList != null) {
                for (Map<String, Object> statementData : statementsList) {
                    String name = (String) statementData.get("name");
                    Integer pageNumber = (Integer) statementData.get("pageNumber");
                    
                    @SuppressWarnings("unchecked")
                    List<String> headers = (List<String>) statementData.get("headers");
                    
                    @SuppressWarnings("unchecked")
                    List<Map<String, Object>> tableDataList = (List<Map<String, Object>>) statementData.get("tableData");
                    
                    List<Map<String, String>> tableData = new ArrayList<>();
                    if (tableDataList != null) {
                        for (Map<String, Object> row : tableDataList) {
                            Map<String, String> stringRow = new HashMap<>();
                            for (Map.Entry<String, Object> entry : row.entrySet()) {
                                stringRow.put(entry.getKey(), entry.getValue() != null ? entry.getValue().toString() : "");
                            }
                            tableData.add(stringRow);
                        }
                    }
                    
                    statements.add(new ProcessingResult.StatementData(name, pageNumber, tableData, headers));
                }
            }
        } catch (Exception e) {
            throw new IOException("Failed to parse JSON response: " + e.getMessage(), e);
        }
        
        return statements;
    }
} 