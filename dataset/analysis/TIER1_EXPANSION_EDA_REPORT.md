# Tier-1 Expansion EDA & Prioritization Report

## 1. Dataset Overview
This analysis investigates the Tier-1 automotive supply-chain dataset to identify the optimal targets for Tier-2 expansion.
- **Number of Focal OEMs**: 19
- **Number of Unique Tier-1 Suppliers**: 830
- **Number of Supplier Relationships (SUPPLIES)**: 1430
- **Number of Suppliers Shared Across Multiple OEMs**: 242

## 2. Geography & Industry
- **Top Countries**: United States of America, Japan, Germany, Korea; Republic (S. Korea), United Kingdom
- **Top Industries**: Auto, Truck & Motorcycle Parts, Software, Auto & Truck Manufacturers, IT Services & Consulting, Electrical Components & Equipment

## 3. Data Quality (Confidence & Freshness)
- Average Confidence: 43.51%
- Average Freshness Score: 2.16 / 5

## 4. Ranking Methodology
Suppliers were ranked using a weighted 0-100 expansion score incorporating:
- OEM Coverage (30%)
- Observed Network Degree (20%)
- Automotive Industry Relevance (15%)
- Relationship Confidence (15%)
- Freshness (10%)
- Evidence / Snippet Count (5%)
- Geographic / Cross-border proxy (5%)

A **greedy coverage algorithm** was then applied to select the TOP 50, 75, and 100 targets. Instead of just picking the highest scores (which might all supply the same OEM), the greedy approach selects the next best supplier that adds connections to focal OEMs not yet covered by the target list.

## 5. Priority Classification
- **Priority A (Top 20%)**: Crucial cross-network bottlenecks and high-relevance nodes.
- **Priority B (Next 30%)**: Strong tier-1 suppliers with good confidence and connectivity.
- **Priority C**: High-quality suppliers providing niche or specific OEM coverage.

## 6. Recommendations for Tier-2 Collection

### Primary Recommendation: TOP 50 List
Collecting the Value Chain data for these 50 suppliers will provide a highly diversified Tier-2 foundation.
- OEMs connected via these targets: 20
- Total direct relationships represented: 315
- Unique Countries: 12

### Alternative Recommendation: TOP 100 List
For a broader expansion covering a long tail of regional or specialized suppliers.
- OEMs connected via these targets: 20
- Total direct relationships represented: 468
- Unique Countries: 19

*Note: All output CSV files and visual charts are available in the `analysis/` directory.*
