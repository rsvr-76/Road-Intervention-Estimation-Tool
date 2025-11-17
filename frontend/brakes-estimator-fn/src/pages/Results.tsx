/**
 * Results Page Component
 * 
 * Displays detailed estimate results with expandable audit trails,
 * sortable tables, and export functionality.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Clock,
  FileText,
  DollarSign,
  SortAsc,
  SortDesc,
  Loader2,
  XCircle,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { 
  getEstimate, 
  exportEstimate, 
  downloadFile,
  type Estimate
} from '../api/client';

type SortField = 'type' | 'quantity' | 'cost' | 'confidence';
type SortDirection = 'asc' | 'desc';

const Results: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // State
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [sortField, setSortField] = useState<SortField>('type');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [exporting, setExporting] = useState<string | null>(null);

  /**
   * Fetch estimate data on mount
   */
  useEffect(() => {
    const fetchEstimate = async () => {
      if (!id) {
        setError('No estimate ID provided');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const data = await getEstimate(id);
        setEstimate(data);
        setError(null);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load estimate';
        setError(errorMessage);
        toast.error(errorMessage);
      } finally {
        setLoading(false);
      }
    };

    fetchEstimate();
  }, [id]);

  /**
   * Toggle row expansion
   */
  const toggleRow = (index: number) => {
    setExpandedRows(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  /**
   * Handle sorting
   */
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  /**
   * Sort items
   */
  const sortedItems = useMemo(() => {
    if (!estimate) return [];

    const items = [...estimate.items];
    
    items.sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (sortField) {
        case 'type':
          aValue = a.intervention.type;
          bValue = b.intervention.type;
          break;
        case 'quantity':
          aValue = a.intervention.quantity;
          bValue = b.intervention.quantity;
          break;
        case 'cost':
          aValue = a.total_cost;
          bValue = b.total_cost;
          break;
        case 'confidence':
          aValue = a.intervention.confidence;
          bValue = b.intervention.confidence;
          break;
        default:
          return 0;
      }

      if (typeof aValue === 'string') {
        return sortDirection === 'asc' 
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      }

      return sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
    });

    return items;
  }, [estimate, sortField, sortDirection]);

  /**
   * Get confidence badge
   */
  const getConfidenceBadge = (confidence: number) => {
    const percent = confidence * 100;
    
    if (percent >= 95) {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-sm">
          <CheckCircle className="w-4 h-4" />
          High Confidence
        </span>
      );
    } else if (percent >= 80) {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-yellow-500/20 text-yellow-400 rounded-full text-sm">
          <AlertCircle className="w-4 h-4" />
          Medium
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-red-500/20 text-red-400 rounded-full text-sm">
          <XCircle className="w-4 h-4" />
          Review Needed
        </span>
      );
    }
  };

  /**
   * Handle export
   */
  const handleExport = async (format: 'csv' | 'json' | 'pdf') => {
    if (!id || !estimate) return;

    try {
      setExporting(format);
      toast.loading(`Exporting as ${format.toUpperCase()}...`);

      const blob = await exportEstimate(id, format);
      const filename = `estimate_${estimate.estimate_id}.${format}`;
      
      downloadFile(blob, filename);
      toast.success(`Downloaded ${filename}`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Export failed';
      toast.error(errorMessage);
    } finally {
      setExporting(null);
    }
  };

  /**
   * Render sort icon
   */
  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? (
      <SortAsc className="w-4 h-4" />
    ) : (
      <SortDesc className="w-4 h-4" />
    );
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-dark flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-white text-lg">Loading estimate...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !estimate) {
    return (
      <div className="min-h-screen bg-dark flex items-center justify-center p-4">
        <div className="bg-darkCard rounded-lg p-8 max-w-md w-full text-center">
          <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-white mb-2">Error Loading Estimate</h2>
          <p className="text-gray-400 mb-6">{error || 'Estimate not found'}</p>
          <button
            onClick={() => navigate('/upload')}
            className="px-6 py-3 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
          >
            Back to Upload
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-dark py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 hover:bg-darkCard rounded-lg transition-colors"
            >
              <ArrowLeft className="w-6 h-6 text-white" />
            </button>
            <div>
              <h1 className="text-3xl font-bold text-white">Estimate Results</h1>
              <p className="text-gray-400">{estimate.filename}</p>
            </div>
          </div>

          {/* Export Buttons */}
          <div className="flex gap-2">
            <button
              onClick={() => handleExport('csv')}
              disabled={exporting !== null}
              className="flex items-center gap-2 px-4 py-2 bg-darkCard text-white rounded-lg hover:bg-gray-700 transition-colors disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              {exporting === 'csv' ? 'Exporting...' : 'CSV'}
            </button>
            <button
              onClick={() => handleExport('json')}
              disabled={exporting !== null}
              className="flex items-center gap-2 px-4 py-2 bg-darkCard text-white rounded-lg hover:bg-gray-700 transition-colors disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              {exporting === 'json' ? 'Exporting...' : 'JSON'}
            </button>
            <button
              onClick={() => handleExport('pdf')}
              disabled={exporting !== null}
              className="flex items-center gap-2 px-4 py-2 bg-darkCard text-white rounded-lg hover:bg-gray-700 transition-colors disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              {exporting === 'pdf' ? 'Exporting...' : 'PDF'}
            </button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-darkCard rounded-lg p-6 shadow-lg">
            <div className="flex items-center gap-3 mb-3">
              <FileText className="w-8 h-8 text-primary" />
              <span className="text-gray-400">Total Interventions</span>
            </div>
            <p className="text-4xl font-bold text-white">{estimate.items.length}</p>
          </div>

          <div className="bg-darkCard rounded-lg p-6 shadow-lg">
            <div className="flex items-center gap-3 mb-3">
              <DollarSign className="w-8 h-8 text-green-500" />
              <span className="text-gray-400">Estimated Cost</span>
            </div>
            <p className="text-4xl font-bold text-white">
              ₹{estimate.total_cost.toLocaleString('en-IN')}
            </p>
          </div>

          <div className="bg-darkCard rounded-lg p-6 shadow-lg">
            <div className="flex items-center gap-3 mb-3">
              <TrendingUp className="w-8 h-8 text-blue-500" />
              <span className="text-gray-400">Avg. Confidence</span>
            </div>
            <p className="text-4xl font-bold text-white">
              {(estimate.confidence * 100).toFixed(0)}%
            </p>
          </div>

          <div className="bg-darkCard rounded-lg p-6 shadow-lg">
            <div className="flex items-center gap-3 mb-3">
              <Clock className="w-8 h-8 text-purple-500" />
              <span className="text-gray-400">Processing Time</span>
            </div>
            <p className="text-4xl font-bold text-white">
              {((estimate.metadata.processing_time_seconds || 0)).toFixed(1)}s
            </p>
          </div>
        </div>

        {/* Interventions Table */}
        <div className="bg-darkCard rounded-lg shadow-lg overflow-hidden">
          <div className="p-6 border-b border-gray-700">
            <h2 className="text-xl font-bold text-white">Interventions Breakdown</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-dark">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-400 uppercase tracking-wider">
                    <button
                      onClick={() => handleSort('type')}
                      className="flex items-center gap-2 hover:text-white transition-colors"
                    >
                      Intervention
                      {renderSortIcon('type')}
                    </button>
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-400 uppercase tracking-wider">
                    <button
                      onClick={() => handleSort('quantity')}
                      className="flex items-center gap-2 hover:text-white transition-colors"
                    >
                      Quantity
                      {renderSortIcon('quantity')}
                    </button>
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-400 uppercase tracking-wider">
                    Materials
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-400 uppercase tracking-wider">
                    IRC Clause
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-400 uppercase tracking-wider">
                    <button
                      onClick={() => handleSort('cost')}
                      className="flex items-center gap-2 hover:text-white transition-colors"
                    >
                      Cost
                      {renderSortIcon('cost')}
                    </button>
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-400 uppercase tracking-wider">
                    <button
                      onClick={() => handleSort('confidence')}
                      className="flex items-center gap-2 hover:text-white transition-colors"
                    >
                      Confidence
                      {renderSortIcon('confidence')}
                    </button>
                  </th>
                  <th className="px-6 py-4 text-center text-sm font-semibold text-gray-400 uppercase tracking-wider">
                    Details
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {sortedItems.map((item, index) => (
                  <React.Fragment key={index}>
                    <tr className="hover:bg-dark/50 transition-colors">
                      <td className="px-6 py-4">
                        <div>
                          <p className="text-white font-semibold capitalize">
                            {item.intervention.type.replace(/_/g, ' ')}
                          </p>
                          <p className="text-sm text-gray-400">
                            {item.intervention.location || 'No location'}
                          </p>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-white">
                        {item.intervention.quantity} {item.intervention.unit}
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-white">{item.materials.length} material(s)</p>
                        {item.materials[0] && (
                          <p className="text-sm text-gray-400">{item.materials[0].name}</p>
                        )}
                      </td>
                      <td className="px-6 py-4 text-white">
                        {item.materials[0]?.irc_clause || 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-white font-semibold">
                        ₹{item.total_cost.toLocaleString('en-IN')}
                      </td>
                      <td className="px-6 py-4">
                        {getConfidenceBadge(item.intervention.confidence)}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <button
                          onClick={() => toggleRow(index)}
                          className="p-2 hover:bg-dark rounded transition-colors"
                        >
                          {expandedRows.has(index) ? (
                            <ChevronUp className="w-5 h-5 text-primary" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-gray-400" />
                          )}
                        </button>
                      </td>
                    </tr>

                    {/* Expanded Audit Trail */}
                    {expandedRows.has(index) && (
                      <tr>
                        <td colSpan={7} className="px-6 py-6 bg-dark">
                          <div className="space-y-6">
                            <h3 className="text-lg font-bold text-white mb-4">Audit Trail</h3>

                            {/* Extraction Details */}
                            {item.audit_trail.extraction && (
                              <div className="bg-darkCard p-4 rounded-lg">
                                <h4 className="text-white font-semibold mb-3">Extraction Details</h4>
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                  <div>
                                    <span className="text-gray-400">Method:</span>
                                    <span className="text-white ml-2">{item.audit_trail.extraction.method}</span>
                                  </div>
                                  <div>
                                    <span className="text-gray-400">Confidence:</span>
                                    <span className="text-white ml-2">
                                      {(item.audit_trail.extraction.confidence * 100).toFixed(1)}%
                                    </span>
                                  </div>
                                  <div>
                                    <span className="text-gray-400">Type:</span>
                                    <span className="text-white ml-2 capitalize">
                                      {item.audit_trail.extraction.type.replace(/_/g, ' ')}
                                    </span>
                                  </div>
                                  <div>
                                    <span className="text-gray-400">Quantity:</span>
                                    <span className="text-white ml-2">
                                      {item.audit_trail.extraction.quantity} {item.audit_trail.extraction.unit}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* IRC Clause */}
                            {item.audit_trail.clause_matching && (
                              <div className="bg-darkCard p-4 rounded-lg">
                                <h4 className="text-white font-semibold mb-3">IRC Clause</h4>
                                <div className="space-y-2 text-sm">
                                  <div>
                                    <span className="text-gray-400">Standard:</span>
                                    <span className="text-white ml-2">
                                      {item.audit_trail.clause_matching.standard || 'N/A'}
                                    </span>
                                  </div>
                                  <div>
                                    <span className="text-gray-400">Clause:</span>
                                    <span className="text-white ml-2">
                                      {item.audit_trail.clause_matching.clause || 'N/A'}
                                    </span>
                                  </div>
                                  <div>
                                    <span className="text-gray-400">Title:</span>
                                    <span className="text-white ml-2">
                                      {item.audit_trail.clause_matching.title || 'N/A'}
                                    </span>
                                  </div>
                                  {item.audit_trail.clause_matching.category && (
                                    <div>
                                      <span className="text-gray-400">Category:</span>
                                      <span className="text-white ml-2">
                                        {item.audit_trail.clause_matching.category}
                                      </span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}

                            {/* Quantity Calculation */}
                            {item.audit_trail.quantity_calculation && (
                              <div className="bg-darkCard p-4 rounded-lg">
                                <h4 className="text-white font-semibold mb-3">Quantity Calculation</h4>
                                <div className="space-y-2 text-sm">
                                  {item.audit_trail.quantity_calculation.formula && (
                                    <div>
                                      <span className="text-gray-400">Formula:</span>
                                      <p className="text-white mt-1 font-mono bg-dark p-2 rounded">
                                        {item.audit_trail.quantity_calculation.formula}
                                      </p>
                                    </div>
                                  )}
                                  {item.audit_trail.quantity_calculation.calculation && (
                                    <div>
                                      <span className="text-gray-400">Calculation:</span>
                                      <p className="text-white mt-1 font-mono bg-dark p-2 rounded">
                                        {item.audit_trail.quantity_calculation.calculation}
                                      </p>
                                    </div>
                                  )}
                                  <div>
                                    <span className="text-gray-400">Result:</span>
                                    <span className="text-white ml-2">
                                      {item.audit_trail.quantity_calculation.result}{' '}
                                      {item.audit_trail.quantity_calculation.unit}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Pricing */}
                            {item.audit_trail.pricing && (
                              <div className="bg-darkCard p-4 rounded-lg">
                                <h4 className="text-white font-semibold mb-3">Pricing Details</h4>
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                  <div>
                                    <span className="text-gray-400">Source:</span>
                                    <span className="text-white ml-2">{item.audit_trail.pricing.source}</span>
                                  </div>
                                  <div>
                                    <span className="text-gray-400">Unit Price:</span>
                                    <span className="text-white ml-2">
                                      ₹{item.audit_trail.pricing.unit_price}
                                    </span>
                                  </div>
                                  <div>
                                    <span className="text-gray-400">Confidence:</span>
                                    <span className="text-white ml-2">
                                      {(item.audit_trail.pricing.confidence * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                  <div>
                                    <span className="text-gray-400">Fetched Date:</span>
                                    <span className="text-white ml-2">
                                      {item.audit_trail.pricing.fetched_date}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Verification */}
                            {item.audit_trail.verification && (
                              <div className="bg-darkCard p-4 rounded-lg">
                                <h4 className="text-white font-semibold mb-3">Verification</h4>
                                <div className="space-y-3">
                                  <div className="flex items-center gap-2">
                                    <CheckCircle className="w-5 h-5 text-green-500" />
                                    <span className="text-white">
                                      {item.audit_trail.verification.checks_passed?.length || 0} checks passed
                                    </span>
                                  </div>
                                  {item.audit_trail.verification.warnings?.length > 0 && (
                                    <div>
                                      <div className="flex items-center gap-2 mb-2">
                                        <AlertCircle className="w-5 h-5 text-yellow-500" />
                                        <span className="text-yellow-400">
                                          {item.audit_trail.verification.warnings.length} warning(s)
                                        </span>
                                      </div>
                                      <ul className="list-disc list-inside text-sm text-gray-400 ml-7">
                                        {item.audit_trail.verification.warnings.map((warning: string, i: number) => (
                                          <li key={i}>{warning}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}

                            {/* Assumptions */}
                            {item.assumptions.length > 0 && (
                              <div className="bg-darkCard p-4 rounded-lg">
                                <h4 className="text-white font-semibold mb-3">Assumptions</h4>
                                <ul className="list-disc list-inside text-sm text-gray-400 space-y-1">
                                  {item.assumptions.map((assumption, i) => (
                                    <li key={i}>{assumption}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Results;
