/**
 * Upload Page Component
 * 
 * Handles PDF file upload with drag-and-drop support,
 * progress tracking, and results display.
 */

import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Upload as UploadIcon, 
  FileText, 
  CheckCircle, 
  XCircle, 
  Loader2,
  AlertCircle,
  TrendingUp,
  Clock,
  DollarSign
} from 'lucide-react';
import toast from 'react-hot-toast';
import { uploadPDF, type EstimateResponse } from '../api/client';

// Constants
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB
const ACCEPTED_TYPE = 'application/pdf';

const Upload: React.FC = () => {
  const navigate = useNavigate();

  // State management
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<EstimateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  /**
   * Validate selected file
   */
  const validateFile = useCallback((selectedFile: File): string | null => {
    // Check file type
    if (selectedFile.type !== ACCEPTED_TYPE) {
      return 'Invalid file type. Please select a PDF file.';
    }

    // Check file size
    if (selectedFile.size > MAX_FILE_SIZE) {
      const sizeMB = (selectedFile.size / (1024 * 1024)).toFixed(2);
      return `File size (${sizeMB} MB) exceeds the 25 MB limit.`;
    }

    return null;
  }, []);

  /**
   * Handle file selection from input
   */
  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile) return;

    const validationError = validateFile(selectedFile);
    if (validationError) {
      setError(validationError);
      toast.error(validationError);
      return;
    }

    setFile(selectedFile);
    setError(null);
    setResult(null);
    toast.success(`File selected: ${selectedFile.name}`);
  }, [validateFile]);

  /**
   * Handle drag events
   */
  const handleDrag = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();

    if (event.type === 'dragenter' || event.type === 'dragover') {
      setDragActive(true);
    } else if (event.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  /**
   * Handle file drop
   */
  const handleDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);

    const droppedFile = event.dataTransfer.files?.[0];
    if (!droppedFile) return;

    const validationError = validateFile(droppedFile);
    if (validationError) {
      setError(validationError);
      toast.error(validationError);
      return;
    }

    setFile(droppedFile);
    setError(null);
    setResult(null);
    toast.success(`File selected: ${droppedFile.name}`);
  }, [validateFile]);

  /**
   * Handle file upload
   */
  const handleUpload = useCallback(async () => {
    if (!file) {
      toast.error('Please select a file first');
      return;
    }

    setUploading(true);
    setProgress(0);
    setError(null);
    setResult(null);

    const uploadToast = toast.loading('Uploading PDF...');

    try {
      // Upload file with progress tracking
      const response = await uploadPDF(file, (progressPercent) => {
        setProgress(progressPercent);
        
        if (progressPercent === 100) {
          toast.loading('Processing document...', { id: uploadToast });
        }
      });

      setResult(response);
      setProgress(100);
      toast.success(
        `Successfully processed ${response.interventions_found} interventions!`,
        { id: uploadToast }
      );

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed';
      setError(errorMessage);
      toast.error(errorMessage, { id: uploadToast });
    } finally {
      setUploading(false);
    }
  }, [file]);

  /**
   * Reset form
   */
  const handleReset = useCallback(() => {
    setFile(null);
    setUploading(false);
    setProgress(0);
    setResult(null);
    setError(null);
  }, []);

  /**
   * View detailed results
   */
  const handleViewDetails = useCallback(() => {
    if (result?.estimate_id) {
      navigate(`/estimate/${result.estimate_id}`);
    }
  }, [result, navigate]);

  return (
    <div className="min-h-screen bg-dark py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            Upload Road Safety Audit Report
          </h1>
          <p className="text-gray-400">
            Upload a PDF report to automatically estimate material costs for road safety interventions
          </p>
        </div>

        {/* Upload Section */}
        {!result && (
          <div className="bg-darkCard rounded-lg p-8 shadow-lg">
            {/* Drag and Drop Zone */}
            <div
              className={`
                border-2 border-dashed rounded-lg p-12 text-center transition-all
                ${dragActive 
                  ? 'border-primary bg-primary/10' 
                  : 'border-gray-600 hover:border-primary/50'
                }
                ${file ? 'bg-primary/5' : ''}
              `}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
            >
              {!file ? (
                <>
                  <UploadIcon className="w-16 h-16 mx-auto mb-4 text-gray-500" />
                  <h3 className="text-xl font-semibold text-white mb-2">
                    Drop PDF file here or click to browse
                  </h3>
                  <p className="text-gray-400 mb-6">
                    Maximum file size: 25 MB
                  </p>
                  <label className="inline-block">
                    <input
                      type="file"
                      accept=".pdf,application/pdf"
                      onChange={handleFileSelect}
                      disabled={uploading}
                      className="hidden"
                    />
                    <span className="px-6 py-3 bg-primary text-white rounded-lg cursor-pointer hover:bg-primary/90 transition-colors inline-block">
                      Select PDF File
                    </span>
                  </label>
                </>
              ) : (
                <div className="space-y-4">
                  <FileText className="w-16 h-16 mx-auto text-primary" />
                  <div>
                    <h3 className="text-xl font-semibold text-white mb-1">
                      {file.name}
                    </h3>
                    <p className="text-gray-400">
                      {(file.size / (1024 * 1024)).toFixed(2)} MB
                    </p>
                  </div>
                  
                  {!uploading && (
                    <div className="flex gap-4 justify-center pt-4">
                      <button
                        onClick={handleUpload}
                        className="px-8 py-3 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors font-semibold"
                      >
                        Upload & Process
                      </button>
                      <button
                        onClick={handleReset}
                        className="px-8 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Progress Bar */}
            {uploading && (
              <div className="mt-8 space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-400 flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {progress < 100 ? 'Uploading...' : 'Processing...'}
                  </span>
                  <span className="text-white font-semibold">{progress}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-primary h-full transition-all duration-300 rounded-full"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                {progress === 100 && (
                  <p className="text-center text-gray-400 text-sm">
                    Extracting text, parsing interventions, and calculating costs...
                  </p>
                )}
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="mt-6 p-4 bg-red-500/10 border border-red-500/50 rounded-lg flex items-start gap-3">
                <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h4 className="text-red-500 font-semibold mb-1">Upload Failed</h4>
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
                <button
                  onClick={handleReset}
                  className="px-4 py-2 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors text-sm"
                >
                  Retry
                </button>
              </div>
            )}
          </div>
        )}

        {/* Results Section */}
        {result && (
          <div className="space-y-6">
            {/* Success Header */}
            <div className="bg-darkCard rounded-lg p-6 shadow-lg">
              <div className="flex items-center gap-3 mb-4">
                <CheckCircle className="w-8 h-8 text-green-500" />
                <div>
                  <h2 className="text-2xl font-bold text-white">
                    Processing Complete!
                  </h2>
                  <p className="text-gray-400">
                    {result.filename}
                  </p>
                </div>
              </div>

              {/* Key Metrics */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
                <div className="bg-dark p-4 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <FileText className="w-5 h-5 text-primary" />
                    <span className="text-gray-400 text-sm">Interventions</span>
                  </div>
                  <p className="text-2xl font-bold text-white">
                    {result.interventions_found}
                  </p>
                </div>

                <div className="bg-dark p-4 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <DollarSign className="w-5 h-5 text-green-500" />
                    <span className="text-gray-400 text-sm">Total Cost</span>
                  </div>
                  <p className="text-2xl font-bold text-white">
                    ₹{result.total_cost.toLocaleString('en-IN')}
                  </p>
                </div>

                <div className="bg-dark p-4 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-5 h-5 text-blue-500" />
                    <span className="text-gray-400 text-sm">Confidence</span>
                  </div>
                  <p className="text-2xl font-bold text-white">
                    {(result.overall_confidence * 100).toFixed(0)}%
                  </p>
                </div>

                <div className="bg-dark p-4 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Clock className="w-5 h-5 text-purple-500" />
                    <span className="text-gray-400 text-sm">Processing Time</span>
                  </div>
                  <p className="text-2xl font-bold text-white">
                    {(result.processing_time_ms / 1000).toFixed(1)}s
                  </p>
                </div>
              </div>
            </div>

            {/* Verification Status */}
            {result.verification && (
              <div className="bg-darkCard rounded-lg p-6 shadow-lg">
                <h3 className="text-lg font-semibold text-white mb-4">
                  Verification Status: {result.verification.status}
                </h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <p className="text-3xl font-bold text-green-500">
                      {result.verification.passed_count}
                    </p>
                    <p className="text-sm text-gray-400">Passed</p>
                  </div>
                  <div className="text-center">
                    <p className="text-3xl font-bold text-yellow-500">
                      {result.verification.warning_count}
                    </p>
                    <p className="text-sm text-gray-400">Warnings</p>
                  </div>
                  <div className="text-center">
                    <p className="text-3xl font-bold text-red-500">
                      {result.verification.error_count}
                    </p>
                    <p className="text-sm text-gray-400">Errors</p>
                  </div>
                </div>
              </div>
            )}

            {/* Items Summary */}
            <div className="bg-darkCard rounded-lg p-6 shadow-lg">
              <h3 className="text-lg font-semibold text-white mb-4">
                Interventions Summary
              </h3>
              <div className="space-y-3">
                {result.items.map((item, index) => (
                  <div
                    key={index}
                    className="bg-dark p-4 rounded-lg flex items-center justify-between"
                  >
                    <div className="flex-1">
                      <h4 className="text-white font-semibold capitalize">
                        {item.intervention_type.replace(/_/g, ' ')}
                      </h4>
                      <p className="text-sm text-gray-400">
                        {item.quantity} {item.unit} • {item.location || 'No location specified'}
                      </p>
                      {item.warnings.length > 0 && (
                        <div className="flex items-center gap-1 mt-1">
                          <AlertCircle className="w-4 h-4 text-yellow-500" />
                          <span className="text-xs text-yellow-500">
                            {item.warnings.length} warning(s)
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-white">
                        ₹{item.total_cost.toLocaleString('en-IN')}
                      </p>
                      <p className="text-xs text-gray-400">
                        {item.materials_count} material(s)
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-4">
              <button
                onClick={handleViewDetails}
                className="flex-1 px-6 py-3 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors font-semibold"
              >
                View Detailed Estimate
              </button>
              <button
                onClick={handleReset}
                className="px-6 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
              >
                Upload Another File
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Upload;
