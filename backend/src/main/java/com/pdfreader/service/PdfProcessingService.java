package com.pdfreader.service;

import com.pdfreader.model.ProcessingResult;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class PdfProcessingService {

    private static final String UPLOAD_DIR = "uploads";
    private static final String OUTPUT_DIR = "output";
    private static final String PYTHON_SCRIPT = "../pdf_processor.py";

    public ProcessingResult processPdf(MultipartFile file) throws IOException {
        // Create directories if they don't exist
        createDirectories();

        // Save uploaded file
        String originalFilename = file.getOriginalFilename();
        String savedFilename = System.currentTimeMillis() + "_" + originalFilename;
        Path uploadPath = Paths.get(UPLOAD_DIR, savedFilename);
        Files.copy(file.getInputStream(), uploadPath);

        try {
            // Run Python script to extract all statements
            ProcessBuilder processBuilder = new ProcessBuilder(
                "python3", "-c", 
                "import sys; sys.path.append('.'); from pdf_processor import extract_all_statements_to_excel; " +
                "extract_all_statements_to_excel('" + uploadPath.toString() + "', '" + OUTPUT_DIR + "', '" + 
                originalFilename.replace(".pdf", "") + "')"
            );
            processBuilder.redirectErrorStream(true);
            
            Process process = processBuilder.start();
            BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()));
            
            StringBuilder output = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line).append("\n");
            }
            
            int exitCode = process.waitFor();
            
            if (exitCode != 0) {
                return new ProcessingResult(null, null, "Python script failed: " + output.toString(), false);
            }

            // Parse Excel file
            List<ProcessingResult.StatementData> statements = parseExcelFile();
            
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
        Files.createDirectories(Paths.get(UPLOAD_DIR));
        Files.createDirectories(Paths.get(OUTPUT_DIR));
    }

    private List<ProcessingResult.StatementData> parseExcelFile() throws IOException {
        List<ProcessingResult.StatementData> statements = new ArrayList<>();
        
        // Look for Excel files in output directory
        File outputDir = new File(OUTPUT_DIR);
        File[] excelFiles = outputDir.listFiles((dir, name) -> name.endsWith(".xlsx"));
        
        if (excelFiles == null || excelFiles.length == 0) {
            return statements;
        }

        // Use the first Excel file found
        try (FileInputStream fis = new FileInputStream(excelFiles[0]);
             Workbook workbook = new XSSFWorkbook(fis)) {

            for (int i = 0; i < workbook.getNumberOfSheets(); i++) {
                Sheet sheet = workbook.getSheetAt(i);
                String sheetName = sheet.getSheetName();
                
                // Extract page number from sheet name or comments
                int pageNumber = extractPageNumber(sheet);
                
                List<String> headers = new ArrayList<>();
                List<Map<String, String>> tableData = new ArrayList<>();
                
                // Read headers from first row
                Row headerRow = sheet.getRow(0);
                if (headerRow != null) {
                    for (Cell cell : headerRow) {
                        headers.add(getCellValueAsString(cell));
                    }
                }
                
                // Read data rows
                for (int rowIndex = 1; rowIndex <= sheet.getLastRowNum(); rowIndex++) {
                    Row row = sheet.getRow(rowIndex);
                    if (row != null) {
                        Map<String, String> rowData = new HashMap<>();
                        for (int colIndex = 0; colIndex < headers.size(); colIndex++) {
                            Cell cell = row.getCell(colIndex);
                            rowData.put(headers.get(colIndex), getCellValueAsString(cell));
                        }
                        tableData.add(rowData);
                    }
                }
                
                statements.add(new ProcessingResult.StatementData(sheetName, pageNumber, tableData, headers));
            }
        }
        
        return statements;
    }

    private int extractPageNumber(Sheet sheet) {
        // Try to extract page number from sheet comments or name
        String sheetName = sheet.getSheetName();
        
        // Look for page number in sheet name
        if (sheetName.contains("Page")) {
            String[] parts = sheetName.split("Page");
            if (parts.length > 1) {
                try {
                    return Integer.parseInt(parts[1].trim());
                } catch (NumberFormatException e) {
                    // Ignore and continue
                }
            }
        }
        
        // Default to 1 if no page number found
        return 1;
    }

    private String getCellValueAsString(Cell cell) {
        if (cell == null) {
            return "";
        }
        
        switch (cell.getCellType()) {
            case STRING:
                return cell.getStringCellValue();
            case NUMERIC:
                if (DateUtil.isCellDateFormatted(cell)) {
                    return cell.getDateCellValue().toString();
                } else {
                    return String.valueOf(cell.getNumericCellValue());
                }
            case BOOLEAN:
                return String.valueOf(cell.getBooleanCellValue());
            case FORMULA:
                return cell.getCellFormula();
            default:
                return "";
        }
    }
} 