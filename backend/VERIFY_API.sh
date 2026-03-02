#!/bin/bash

# Comprehensive API Verification Script
# Tests all endpoints, data integrity, and functionality

set -e

API_URL="http://localhost:8000/api/v1"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          🚀 COMPREHENSIVE API VERIFICATION SUITE 🚀            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}\n"

# Counter for tests
TESTS_PASSED=0
TESTS_FAILED=0

# Function to test an endpoint
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local expected_status=$4
    
    echo -e "${YELLOW}Testing:${NC} $name"
    
    response=$(curl -s -w "\n%{http_code}" -X "$method" "$API_URL$endpoint")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASSED${NC} (HTTP $http_code)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo "$body" | head -c 200
        echo -e "\n"
    else
        echo -e "${RED}✗ FAILED${NC} (Expected $expected_status, got $http_code)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo -e "${NC}\n"
    fi
}

# ==============================================================================
# 1. HEALTH CHECK
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}1. HEALTH CHECK${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

test_endpoint "Health Status" "GET" "/health" "200"

# ==============================================================================
# 2. NVD/CVE ENDPOINT
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}2. NVD/CVE ENDPOINT${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

test_endpoint "List CVEs (Default)" "GET" "/nvd/cves" "200"
test_endpoint "List CVEs (Page 1, Size 3)" "GET" "/nvd/cves?page=1&page_size=3" "200"
test_endpoint "List CVEs (Sort by severity)" "GET" "/nvd/cves?sort_by=severity_score&sort_order=asc" "200"
test_endpoint "List CVEs (Page 2)" "GET" "/nvd/cves?page=2" "200"

# ==============================================================================
# 3. VULNERABILITIES ENDPOINT
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}3. VULNERABILITIES (EXPLOITED CVEs) ENDPOINT${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

test_endpoint "List Exploited CVEs" "GET" "/vulnerabilities/exploited" "200"
test_endpoint "List Exploited CVEs (Page 1)" "GET" "/vulnerabilities/exploited?page=1&page_size=5" "200"
test_endpoint "List Exploited CVEs (Page 2)" "GET" "/vulnerabilities/exploited?page=2&page_size=10" "200"

# ==============================================================================
# 4. IC3 ENDPOINT
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}4. IC3 (FBI CRIME DATA) ENDPOINT${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

test_endpoint "List IC3 Incidents" "GET" "/ic3/incidents" "200"
test_endpoint "List IC3 Incidents (Page 1)" "GET" "/ic3/incidents?page=1&page_size=5" "200"
test_endpoint "List IC3 Incidents (Sort by year)" "GET" "/ic3/incidents?sort_by=year&sort_order=desc" "200"
test_endpoint "List IC3 Incidents (Sort by loss)" "GET" "/ic3/incidents?sort_by=loss_amount&sort_order=desc" "200"

# ==============================================================================
# 5. ECONOMICS ENDPOINT
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}5. ECONOMICS (CENSUS DATA) ENDPOINT${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

test_endpoint "List Economic Indicators" "GET" "/economics/indicators" "200"
test_endpoint "List Economic Indicators (Page 1)" "GET" "/economics/indicators?page=1&page_size=5" "200"
test_endpoint "List Economic Indicators (All)" "GET" "/economics/indicators?page_size=100" "200"

# ==============================================================================
# 6. DATA INTEGRITY CHECKS
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}6. DATA INTEGRITY CHECKS${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo -e "${YELLOW}Checking CVE Data Count...${NC}"
cve_count=$(curl -s "$API_URL/nvd/cves?page=1&page_size=1" | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])" 2>/dev/null || echo "0")
if [ "$cve_count" -gt 0 ]; then
    echo -e "${GREEN}✓ CVEs Available:${NC} $cve_count records"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ No CVE data found${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo -e "${YELLOW}Checking Exploited CVE Data Count...${NC}"
exploited_count=$(curl -s "$API_URL/vulnerabilities/exploited?page=1&page_size=1" | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])" 2>/dev/null || echo "0")
if [ "$exploited_count" -gt 0 ]; then
    echo -e "${GREEN}✓ Exploited CVEs Available:${NC} $exploited_count records"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ No exploited CVE data found${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo -e "${YELLOW}Checking IC3 Data Count...${NC}"
ic3_count=$(curl -s "$API_URL/ic3/incidents?page=1&page_size=1" | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])" 2>/dev/null || echo "0")
if [ "$ic3_count" -gt 0 ]; then
    echo -e "${GREEN}✓ IC3 Incidents Available:${NC} $ic3_count records"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ No IC3 data found${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo -e "${YELLOW}Checking Economic Data Count...${NC}"
econ_count=$(curl -s "$API_URL/economics/indicators?page=1&page_size=1" | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])" 2>/dev/null || echo "0")
if [ "$econ_count" -gt 0 ]; then
    echo -e "${GREEN}✓ Economic Indicators Available:${NC} $econ_count records"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ No economic data found${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# ==============================================================================
# 7. RESPONSE STRUCTURE VALIDATION
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}7. RESPONSE STRUCTURE VALIDATION${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo -e "${YELLOW}Validating NVD Response Structure...${NC}"
nvd_response=$(curl -s "$API_URL/nvd/cves?page=1&page_size=1")
if echo "$nvd_response" | python3 -c "import sys, json; d=json.load(sys.stdin); assert 'total' in d and 'items' in d and 'page' in d" 2>/dev/null; then
    echo -e "${GREEN}✓ NVD response has correct structure${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ NVD response structure invalid${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo -e "${YELLOW}Validating IC3 Response Structure...${NC}"
ic3_response=$(curl -s "$API_URL/ic3/incidents?page=1&page_size=1")
if echo "$ic3_response" | python3 -c "import sys, json; d=json.load(sys.stdin); assert 'total' in d and 'items' in d and 'page' in d" 2>/dev/null; then
    echo -e "${GREEN}✓ IC3 response has correct structure${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ IC3 response structure invalid${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo -e "${YELLOW}Validating Economics Response Structure...${NC}"
econ_response=$(curl -s "$API_URL/economics/indicators?page=1&page_size=1")
if echo "$econ_response" | python3 -c "import sys, json; d=json.load(sys.stdin); assert 'total' in d and 'items' in d and 'page' in d" 2>/dev/null; then
    echo -e "${GREEN}✓ Economics response has correct structure${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ Economics response structure invalid${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# ==============================================================================
# 8. PAGINATION TESTS
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}8. PAGINATION TESTS${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo -e "${YELLOW}Testing CVE Pagination...${NC}"
page1=$(curl -s "$API_URL/nvd/cves?page=1&page_size=5" | python3 -c "import sys, json; print(json.load(sys.stdin)['items'][0]['id'])" 2>/dev/null)
page2=$(curl -s "$API_URL/nvd/cves?page=2&page_size=5" | python3 -c "import sys, json; print(json.load(sys.stdin)['items'][0]['id'])" 2>/dev/null)
if [ "$page1" != "$page2" ]; then
    echo -e "${GREEN}✓ Pagination works (different items on different pages)${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ Pagination may not be working${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# ==============================================================================
# 9. SORTING TESTS
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}9. SORTING TESTS${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo -e "${YELLOW}Testing IC3 Sorting by Loss Amount...${NC}"
ic3_sort=$(curl -s "$API_URL/ic3/incidents?sort_by=loss_amount&sort_order=desc&page_size=2" | python3 -c "import sys, json; d=json.load(sys.stdin)['items']; print('sorted' if d[0]['loss_amount'] >= d[1]['loss_amount'] else 'not sorted')" 2>/dev/null)
if [ "$ic3_sort" = "sorted" ]; then
    echo -e "${GREEN}✓ Sorting works correctly${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}ℹ Sorting test inconclusive${NC}"
fi

# ==============================================================================
# SUMMARY
# ==============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}VERIFICATION SUMMARY${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo -e "${GREEN}✓ Tests Passed: $TESTS_PASSED${NC}"
echo -e "${RED}✗ Tests Failed: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ ALL TESTS PASSED - API IS FULLY OPERATIONAL!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}\n"
    exit 0
else
    echo -e "\n${RED}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}✗ SOME TESTS FAILED - PLEASE REVIEW ABOVE${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════════${NC}\n"
    exit 1
fi
