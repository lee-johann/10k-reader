package com.pdfreader.controller;

import com.pdfreader.service.PdfProcessingService;
import com.pdfreader.model.ProcessingResult;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;

@RestController
@RequestMapping("/api/pdf")
@CrossOrigin(origins = "http://localhost:3000")
public class PdfController {

    @Autowired
    private PdfProcessingService pdfProcessingService;

    @GetMapping("/documents")
    public ResponseEntity<List<String>> getAvailablePdfs() {
        List<String> pdfs = pdfProcessingService.getAvailablePdfs();
        return ResponseEntity.ok(pdfs);
    }

    @PostMapping("/process-document")
    public ResponseEntity<ProcessingResult> processDocument(@RequestParam("filename") String filename) {
        try {
            ProcessingResult result = pdfProcessingService.processPdfFromDocuments(filename);
            return ResponseEntity.ok(result);
        } catch (IOException e) {
            return ResponseEntity.badRequest().build();
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }

    @PostMapping("/upload")
    public ResponseEntity<ProcessingResult> uploadAndProcessPdf(@RequestParam("file") MultipartFile file) {
        try {
            ProcessingResult result = pdfProcessingService.processPdf(file);
            return ResponseEntity.ok(result);
        } catch (IOException e) {
            return ResponseEntity.badRequest().build();
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }

    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("Backend is running!");
    }
} 